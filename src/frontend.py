"""
The Final Battle - Pygame Frontend (Polished).
Smooth pixel walking, real tile sprites, correct character sprites.
"""

import os
import sys
import argparse
import pygame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from game import GameSession, load_json, ASSET_DIR, BASE_DIR
from sprite_extractor import SpriteExtractor
from asset_generator import generate_all as generate_assets
try:
    from map_renderer import NIGHT_MODE
except ImportError:
    NIGHT_MODE = False
# ---------- constants -------------------------------------------------------
TILE_SIZE = 48
VIEW_TILES_X = 15
VIEW_TILES_Y = 11
SCREEN_W = TILE_SIZE * VIEW_TILES_X
HUD_H = 90
SCREEN_H = TILE_SIZE * VIEW_TILES_Y + HUD_H
FPS = 60

# Walk smoothing
WALK_FRAMES = 12  # frames to walk one tile (smooth)

# Colors
C_BG = (20, 20, 30)
C_WHITE = (255, 255, 255)
C_BLACK = (0, 0, 0)
C_RED = (200, 50, 50)
C_GREEN = (50, 200, 50)
C_BLUE = (50, 100, 220)
C_PANEL = (25, 25, 45)
C_HIGHLIGHT = (255, 255, 80)
C_GREY = (140, 140, 140)
C_DARK = (15, 15, 25)

# Tile fallback colors
TILE_COLORS = {
    ".": (114, 204, 164), "g": (79, 164, 101), "d": (197, 188, 139),
    "p": (174, 178, 188), "s": (197, 188, 139), "S": (197, 188, 139),
    "1": (107, 188, 113), "2": (101, 180, 102), "3": (87, 165, 76),
    "4": (85, 164, 75), "T": (84, 169, 103), "C": (110, 199, 149),
    "w": (74, 128, 222), "W": (78, 108, 177), "R": (206, 100, 90),
    "r": (218, 108, 93), "L": (91, 153, 212), "l": (106, 174, 230),
    "D": (132, 124, 125), "f": (172, 174, 183), "B": (70, 121, 206),
    "A": (200, 201, 162), "F": (86, 118, 183),
    "N": (185, 150, 95),
}

# Tile char -> asset filename
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
    "f": "tile_fence.png",
    "w": "tile_water.png",
    "W": "tile_water_edge_t.png",
    "R": "tile_rock.png",
    "L": "tile_wall_l.png",
    "l": "tile_wall_r.png",
    "D": "tile_door.png",
    "B": "tile_bridge.png",
    "A": "tile_arena.png",
    "z": "tile_dirt.png",
    "K": "tile_door.png",
    "O": "tile_path.png",
    "Q": "tile_door.png",
    "P": "tile_door.png",
    "M": "tile_wall.png",
    "N": "tile_sign.png",
    "b": "tile_rock.png",
}


# ---------- Asset Manager ---------------------------------------------------

class Assets:
    def __init__(self, extractor):
        self.extractor = extractor
        self.tiles = {}
        self.players = {}   # prefix -> {direction -> [frame0, frame1, frame2]}
        self.surf = {}      # prefix -> {"ride": {dir->img}, "mount": {dir->img}}
        self.creatures = {}
        self.rock_smash_frames = []  # 4 frames for rock break animation
        self._load_tiles()
        self._load_npc()
        self._load_rock_smash()

    def _img(self, path, size=None):
        if not os.path.exists(path):
            return None
        try:
            img = pygame.image.load(path).convert_alpha()
            if size:
                img = pygame.transform.smoothscale(img, size)
            return img
        except:
            return None

    def _load_tiles(self):
        for ch, fname in TILE_FILES.items():
            s = self._img(os.path.join(ASSET_DIR, fname), (TILE_SIZE, TILE_SIZE))
            if s:
                if NIGHT_MODE:
                    # night-tint fallback tiles (I, N overlays) to match dark map
                    try:
                        # subtle darken + blue shift via multiply then alpha overlay
                        mult = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                        mult.fill((138, 140, 180, 255))
                        s.blit(mult, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                        overlay = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                        overlay.fill((18, 20, 48, 28))
                        s.blit(overlay, (0, 0))
                    except Exception:
                        pass
                self.tiles[ch] = s
            else:
                surf = pygame.Surface((TILE_SIZE, TILE_SIZE))
                surf.fill(TILE_COLORS.get(ch, C_BG))
                self.tiles[ch] = surf

    def _load_npc(self):
        self.npcs = {}
        npc_files = ["npc_fisher", "npc_boy", "npc_girl", "npc_oldman", "npc_hiker", "npc_scientist", "npc_brock", "npc_lance", "npc_blaine"]
        for name in npc_files:
            s = self._img(os.path.join(ASSET_DIR, f"{name}.png"), (TILE_SIZE, TILE_SIZE * 2))
            if s:
                self.npcs[name] = s
        # fallback
        self.npc = self.npcs.get("npc_boy")
        # trainer faces (battaglia) — presi dalla ROM (front pics Red/Leaf/Rival) a runtime
        self.trainer_faces = {}
        self._load_trainer_faces()

    def _load_rock_smash(self):
        """Load rock smash animation frames from assets/ (generated from sprites.json)."""
        self.rock_smash_frames = []
        for i in range(4):
            path = os.path.join(ASSET_DIR, f"tile_rock_smash_{i}.png")
            if os.path.exists(path):
                surf = self._img(path, (TILE_SIZE, TILE_SIZE))
                if surf:
                    self.rock_smash_frames.append(surf)

    def _load_trainer_faces(self):
        self.trainer_faces = {}
        ow_fallback = {
            "red": "player_red",
            "leaf": "player_green",
            "green": "player_green",
            "blue": "player_blue",
            "brock": "npc_brock",
            "rival_early": "player_blue",
            "rival_late": "player_blue",
            "champion_rival": "player_blue",
        }
        for char_id in list(ow_fallback.keys()):
            face_path = os.path.join(ASSET_DIR, f"trainer_{char_id}.png")
            img = None
            if os.path.exists(face_path):
                try:
                    from PIL import Image as PILImage
                    pil = PILImage.open(face_path).convert("RGBA")
                    pil = pil.resize((48, 48), PILImage.NEAREST)
                    tmp = f"/tmp/trainer_face_{char_id}.png"
                    pil.save(tmp)
                    img = self._img(tmp, (48, 48))
                except Exception:
                    img = None
            if img is None:
                prefix = ow_fallback.get(char_id, "player_red")
                self.load_player(prefix)
                img = self.player_frame(prefix, "down", 0)
                if img:
                    try:
                        img = pygame.transform.scale(img, (48, 48))
                    except Exception:
                        pass
            if img:
                self.trainer_faces[char_id] = img

    def get_trainer_face(self, char_id):
        return self.trainer_faces.get(char_id) or self.trainer_faces.get("red")

    def get_npc_sprite(self, sprite_name):
        return self.npcs.get(sprite_name, self.npc)

    def load_player(self, prefix):
        if prefix in self.players:
            return
        dirs_files = {
            "down": [f"{prefix}_down.png", f"{prefix}_walk_down_1.png", f"{prefix}_walk_down_2.png"],
            "up": [f"{prefix}_up.png", f"{prefix}_walk_up_1.png", f"{prefix}_walk_up_2.png"],
            "left": [f"{prefix}_left.png", f"{prefix}_walk_left_1.png", f"{prefix}_walk_left_2.png"],
        }
        sp = {}
        for d, files in dirs_files.items():
            frames = []
            for fn in files:
                f = self._img(os.path.join(ASSET_DIR, fn), (TILE_SIZE, TILE_SIZE * 2))
                if f:
                    frames.append(f)
            if frames:
                sp[d] = frames
        if "left" in sp:
            sp["right"] = [pygame.transform.flip(f, True, False) for f in sp["left"]]
        self.players[prefix] = sp

    def player_frame(self, prefix, direction, anim_tick):
        """Get the right walk frame. anim_tick goes from 0..WALK_FRAMES-1 during a step."""
        if prefix not in self.players:
            self.load_player(prefix)
        frames = self.players.get(prefix, {}).get(direction, [])
        if not frames:
            return None
        if anim_tick == 0:
            return frames[0]  # idle
        # alternate between walk frame 1 and 2
        idx = 1 + (anim_tick // (WALK_FRAMES // 2)) % max(1, len(frames) - 1)
        return frames[min(idx, len(frames) - 1)]

    def load_surf(self, prefix):
        if prefix in self.surf:
            return
        s = {"ride": {}, "mount": {}}
        for d, fname in [("down", f"{prefix}_surf_down.png"),
                         ("up", f"{prefix}_surf_up.png"),
                         ("left", f"{prefix}_surf_left.png")]:
            img = self._img(os.path.join(ASSET_DIR, fname), (TILE_SIZE, TILE_SIZE * 2))
            if img:
                s["ride"][d] = img
        if "left" in s["ride"]:
            s["ride"]["right"] = pygame.transform.flip(s["ride"]["left"], True, False)
        for d, fname in [("down", f"{prefix}_surf_mount_down.png"),
                         ("up", f"{prefix}_surf_mount_up.png"),
                         ("left", f"{prefix}_surf_mount_left.png")]:
            img = self._img(os.path.join(ASSET_DIR, fname), (TILE_SIZE, TILE_SIZE * 2))
            if img:
                s["mount"][d] = img
        if "left" in s["mount"]:
            s["mount"]["right"] = pygame.transform.flip(s["mount"]["left"], True, False)
        self.surf[prefix] = s

    def surf_frame(self, prefix, direction, mount=False):
        """Return the surfing sprite for a direction (riding idle or mount frame)."""
        if prefix not in self.surf:
            self.load_surf(prefix)
        s = self.surf.get(prefix)
        if not s:
            return None
        table = s["mount"] if mount else s["ride"]
        return table.get(direction)

    def get_tile(self, ch):
        return self.tiles.get(ch, self.tiles.get("."))

    def get_creature(self, species_id, size=(48, 48)):
        key = (species_id, size)
        if key in self.creatures:
            return self.creatures[key]
        path = self.extractor.get_creature_sprite_path(species_id)
        if path:
            s = self._img(path, size)
            if s:
                self.creatures[key] = s
                return s
        # fallback
        surf = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.circle(surf, C_RED, (size[0]//2, size[1]//2), size[0]//3)
        self.creatures[key] = surf
        return surf


# ---------- Smooth Walker ---------------------------------------------------

class SmoothWalker:
    """Handles pixel-smooth walking between tiles."""
    def __init__(self):
        self.walking = False
        self.anim_tick = 0      # 0 = idle, 1..WALK_FRAMES = walking
        self.offset_x = 0.0     # pixel offset from current tile
        self.offset_y = 0.0
        self.dir_x = 0
        self.dir_y = 0
        self.step_count = 0     # total steps for alternating left/right foot

    def start_step(self, dx, dy):
        self.walking = True
        self.anim_tick = 1
        self.dir_x = dx
        self.dir_y = dy
        self.step_count += 1

    def update(self):
        """Call each frame. Returns True when step completes."""
        if not self.walking:
            self.offset_x = 0
            self.offset_y = 0
            return False
        self.anim_tick += 1
        progress = self.anim_tick / WALK_FRAMES
        self.offset_x = self.dir_x * progress * TILE_SIZE
        self.offset_y = self.dir_y * progress * TILE_SIZE
        if self.anim_tick >= WALK_FRAMES:
            self.walking = False
            self.anim_tick = 0
            self.offset_x = 0
            self.offset_y = 0
            return True  # step complete
        return False

    def reset(self):
        """Reset walker to idle state (used on map transitions)."""
        self.walking = False
        self.anim_tick = 0
        self.offset_x = 0
        self.offset_y = 0
        self.dir_x = 0
        self.dir_y = 0

    def get_render_offset(self):
        return self.offset_x, self.offset_y


# ---------- Camera ----------------------------------------------------------

class Camera:
    def __init__(self, map_w, map_h):
        self.map_w = map_w
        self.map_h = map_h
        self.x = 0.0
        self.y = 0.0

    def update(self, player_pixel_x, player_pixel_y):
        # center on player
        target_x = player_pixel_x - (VIEW_TILES_X // 2) * TILE_SIZE
        target_y = player_pixel_y - (VIEW_TILES_Y // 2) * TILE_SIZE
        max_x = self.map_w * TILE_SIZE - VIEW_TILES_X * TILE_SIZE
        max_y = self.map_h * TILE_SIZE - VIEW_TILES_Y * TILE_SIZE
        target_x = max(0, min(target_x, max_x))
        target_y = max(0, min(target_y, max_y))
        # smooth follow
        self.x += (target_x - self.x) * 0.2
        self.y += (target_y - self.y) * 0.2

    def to_screen(self, world_px, world_py):
        return int(world_px - self.x), int(world_py - self.y)


# ---------- Drawing ---------------------------------------------------------

def draw_map(surface, session, assets, camera, rock_break_anim=None):
    """Draw map using pre-rendered background image (authentic retro RPG look)."""
    if not hasattr(assets, 'map_bg') or assets.map_bg is None:
        bg_file = session.get_current_map().get("background")
        if bg_file:
            bg_path = os.path.join(ASSET_DIR, bg_file)
            if os.path.exists(bg_path):
                raw = pygame.image.load(bg_path).convert()
                scale_factor = TILE_SIZE / 16
                new_w = int(raw.get_width() * scale_factor)
                new_h = int(raw.get_height() * scale_factor)
                assets.map_bg = pygame.transform.scale(raw, (new_w, new_h))
            else:
                assets.map_bg = None
        else:
            assets.map_bg = None
    if assets.map_bg:
        src_rect = pygame.Rect(int(camera.x), int(camera.y),
                               VIEW_TILES_X * TILE_SIZE, VIEW_TILES_Y * TILE_SIZE)
        surface.blit(assets.map_bg, (0, 0), src_rect)
        # Overlay: hide cut trees (paint path), show items (I)
        layout = session.get_current_map()["layout"]
        start_col = max(0, int(camera.x // TILE_SIZE) - 1)
        start_row = max(0, int(camera.y // TILE_SIZE) - 1)
        end_col = min(len(layout[0]) if layout else 0, start_col + VIEW_TILES_X + 3)
        end_row = min(len(layout), start_row + VIEW_TILES_Y + 3)
        for row in range(start_row, end_row):
            for col in range(start_col, end_col):
                ch = session.get_tile_at(col, row)
                if row < len(layout) and col < len(layout[row]):
                    orig_ch = layout[row][col]
                else:
                    orig_ch = None
                sx, sy = camera.to_screen(col * TILE_SIZE, row * TILE_SIZE)
                if orig_ch == "C" and ch == "d":
                    # Tree was cut - paint over with BG path color
                    # Extract matching tile from BG row above (pure path)
                    if assets.map_bg:
                        src_x = col * TILE_SIZE
                        # Use row-1 from BG (known to be path)
                        src_y = (row - 1) * TILE_SIZE
                        bg_w = assets.map_bg.get_width()
                        bg_h = assets.map_bg.get_height()
                        if src_x + TILE_SIZE <= bg_w and src_y + TILE_SIZE <= bg_h:
                            patch = assets.map_bg.subsurface((src_x, src_y, TILE_SIZE, TILE_SIZE))
                            surface.blit(patch, (sx, sy))
                elif orig_ch == "R" and ch == "z":
                    # Rock was broken - paint sand tile over the rock
                    tile_surf = assets.get_tile("z")
                    surface.blit(tile_surf, (sx, sy))
                elif orig_ch == "R" and ch == "R":
                    # Rock still present - draw rock sprite overlay
                    tile_surf = assets.get_tile("R")
                    surface.blit(tile_surf, (sx, sy))
                elif ch == "I":
                    # Item still present - draw pokeball overlay
                    tile_surf = assets.get_tile("I")
                    surface.blit(tile_surf, (sx, sy))
                elif orig_ch == "N":
                    # Sign post - always draw overlay to ensure visibility
                    tile_surf = assets.get_tile("N")
                    surface.blit(tile_surf, (sx, sy))
    else:
        layout = session.get_current_map()["layout"]
        start_col = max(0, int(camera.x // TILE_SIZE) - 1)
        start_row = max(0, int(camera.y // TILE_SIZE) - 1)
        end_col = min(len(layout[0]), start_col + VIEW_TILES_X + 3)
        end_row = min(len(layout), start_row + VIEW_TILES_Y + 3)
        for row in range(start_row, end_row):
            for col in range(start_col, end_col):
                ch = session.get_tile_at(col, row)
                tile_surf = assets.get_tile(ch)
                sx, sy = camera.to_screen(col * TILE_SIZE, row * TILE_SIZE)
                surface.blit(tile_surf, (sx, sy))
    # Night ambient overlay over the map viewport (doesn't affect HUD)
    if NIGHT_MODE:
        # Use set_alpha fallback if BLEND_RGBA_MULT not available
        try:
            night = pygame.Surface((VIEW_TILES_X * TILE_SIZE, VIEW_TILES_Y * TILE_SIZE), pygame.SRCALPHA)
            night.fill((18, 20, 48, 38))
            surface.blit(night, (0, 0))
        except Exception:
            pass
    # Rock break animation overlay
    if rock_break_anim is not None:
        # Draw the animation frame
        frame_idx = rock_break_anim["frame"]
        if assets.rock_smash_frames and frame_idx < len(assets.rock_smash_frames):
            frame = assets.rock_smash_frames[frame_idx]
            # frame is a pygame Surface - scale and blit
            frame_surf = pygame.transform.scale(frame, (TILE_SIZE, TILE_SIZE))
            sx, sy = camera.to_screen(rock_break_anim["x"] * TILE_SIZE, rock_break_anim["y"] * TILE_SIZE)
            surface.blit(frame_surf, (sx, sy))
        # Update animation
        rock_break_anim["ticks"] += 1
        if rock_break_anim["ticks"] >= 8:  # 8 ticks per frame
            rock_break_anim["ticks"] = 0
            rock_break_anim["frame"] += 1
            if rock_break_anim["frame"] >= 4:  # Animation complete
                # Replace rock tile in layout with sand
                rx, ry = rock_break_anim["x"], rock_break_anim["y"]
                layout = session.get_current_map().get("layout", [])
                if 0 <= ry < len(layout) and 0 <= rx < len(layout[ry]):
                    row_list = list(layout[ry])
                    if row_list[rx] == 'R':
                        row_list[rx] = 'z'
                        layout[ry] = "".join(row_list)
                rock_break_anim = None
    # Sandstorm effect for desert maps
    if session.current_map_key in ("rock_desert", "rock_desert_arena", "rock_desert_shelter"):
        try:
            import random
            sandstorm = pygame.Surface((VIEW_TILES_X * TILE_SIZE, VIEW_TILES_Y * TILE_SIZE), pygame.SRCALPHA)
            for _ in range(15):  # 15 sand particles
                x = random.randint(0, VIEW_TILES_X * TILE_SIZE)
                y = random.randint(0, VIEW_TILES_Y * TILE_SIZE)
                size = random.randint(2, 5)
                alpha = random.randint(30, 80)
                pygame.draw.rect(sandstorm, (210, 180, 120, alpha), (x, y, size, size))
            surface.blit(sandstorm, (0, 0))
        except Exception:
            pass


def draw_ai(surface, session, assets, camera):
    # IA Blue/Brock visible only on same map as player
    if not hasattr(session, "ai_map_key") or session.ai_map_key != session.current_map_key:
        return
    if not session.opponent:
        return
    opp_char = session.characters.get(session.opponent.character_id, {})
    prefix = opp_char.get("sprite_prefix", "player_blue")
    # usa direzione IA
    direction = getattr(session, "ai_direction", "down")
    layout = session.map_data.get(session.ai_map_key, {}).get("layout", [])
    tile = layout[session.ai_y][session.ai_x] if (
        0 <= session.ai_y < len(layout)
        and session.ai_x < len(layout[session.ai_y])
    ) else None
    # Try player-style directional sprites first (for "player_blue", "player_red", etc.)
    frame = None
    if prefix.startswith("player_"):
        assets.load_player(prefix)
        if getattr(session, "ai_has_surf", False) and tile in ("w", "B"):
            surf_frame = assets.surf_frame(prefix, direction, mount=False)
            if surf_frame:
                sx, sy = camera.to_screen(session.ai_x * TILE_SIZE, session.ai_y * TILE_SIZE)
                surface.blit(surf_frame, (sx, sy - TILE_SIZE))
                return
        frame = assets.player_frame(prefix, direction, 0)
        if not frame:
            frame = assets.player_frame(prefix, "down", 0)
    # Fallback: use NPC single-frame sprite (for "npc_brock", etc.)
    if not frame:
        frame = assets.get_npc_sprite(prefix)
        # Force reload if not found yet
        if not frame and hasattr(assets, '_load_npc'):
            assets._load_npc()
            frame = assets.get_npc_sprite(prefix)
    if frame:
        sx, sy = camera.to_screen(session.ai_x * TILE_SIZE, session.ai_y * TILE_SIZE)
        surface.blit(frame, (sx, sy - TILE_SIZE))

def draw_npcs(surface, session, assets, camera):
    for npc in session.get_current_map().get("npcs", []):
        sx, sy = camera.to_screen(npc["x"] * TILE_SIZE, npc["y"] * TILE_SIZE)
        sprite = None
        # Dynamic rival: use opponent character sprite (player sprite facing down)
        if npc.get("name") == "Rival" and hasattr(session, "opponent") and session.opponent:
            opp_char = session.characters.get(session.opponent.character_id, {})
            prefix = opp_char.get("sprite_prefix", "player_red")
            assets.load_player(prefix)
            sprite = assets.player_frame(prefix, "down", 0)
        if not sprite:
            sprite_name = npc.get("sprite", "npc_boy")
            sprite = assets.get_npc_sprite(sprite_name)
        if sprite:
            surface.blit(sprite, (sx, sy - TILE_SIZE))

def draw_player(surface, session, assets, camera, walker, surf_transition=None):
    prefix = session.characters.get(session.player.character_id, {}).get("sprite_prefix", "player")
    direction = session.player.direction
    ox, oy = walker.get_render_offset()
    # player world pixel position (from PREVIOUS tile + offset)
    px = session.player.x * TILE_SIZE + ox - (TILE_SIZE if walker.walking else 0) * walker.dir_x
    py = session.player.y * TILE_SIZE + oy - (TILE_SIZE if walker.walking else 0) * walker.dir_y
    # Actually simpler: during walk, player pos already updated, offset goes from -TILE to 0
    if walker.walking:
        px = session.player.x * TILE_SIZE - (1 - walker.anim_tick / WALK_FRAMES) * walker.dir_x * TILE_SIZE
        py = session.player.y * TILE_SIZE - (1 - walker.anim_tick / WALK_FRAMES) * walker.dir_y * TILE_SIZE
    else:
        px = session.player.x * TILE_SIZE
        py = session.player.y * TILE_SIZE

    sx, sy = camera.to_screen(px, py)

    surfing = getattr(session.player, "surfing", False)

    if surfing or surf_transition:
        # Mount/dismount transition (or a lingering get-off anim) shows the
        # get-on/off frame for its whole duration.
        if surf_transition:
            frame = assets.surf_frame(prefix, surf_transition.get("dir", direction), mount=True)
            rise = 2 if surf_transition.get("type") == "mount" else 0
        else:
            frame = assets.surf_frame(prefix, direction, mount=False)
            rise = 0
        if not frame:
            frame = assets.player_frame(prefix, direction, 0)
            rise = 0
        if not frame:
            frame = assets.get_npc_sprite(prefix)
        if frame:
            surface.blit(frame, (sx, sy - TILE_SIZE - rise))
            return
        # fall through to blue box fallback
    else:
        frame = assets.player_frame(prefix, direction, walker.anim_tick)
        if not frame:
            frame = assets.player_frame(prefix, "down", 0)
        if not frame:
            frame = assets.get_npc_sprite(prefix)
        if frame:
            surface.blit(frame, (sx, sy - TILE_SIZE))
            return

    pygame.draw.rect(surface, C_BLUE, (sx, sy, TILE_SIZE, TILE_SIZE))


def draw_team_hud(surface, session, assets, font):
    """Player team in top-left with semi-transparent background + faccia allenatore presa dalla ROM."""
    hud_bg = pygame.Surface((285, 54), pygame.SRCALPHA)
    hud_bg.fill((0, 0, 0, 100))
    surface.blit(hud_bg, (0, 0))
    # faccia player (battaglia) a sx
    if session.player:
        face = assets.get_trainer_face(session.player.character_id)
        if face:
            surface.blit(face, (2, 3))
    off = 52
    for i, creature in enumerate(session.player.team[:6]):
        sprite = assets.get_creature(creature.species_id, (40, 40))
        x = off + i * 38
        surface.blit(sprite, (x, 2))
        # HP bar
        ratio = creature.hp / creature.max_hp
        color = C_GREEN if ratio > 0.5 else C_HIGHLIGHT if ratio > 0.25 else C_RED
        pygame.draw.rect(surface, (40, 40, 40), (x, 43, 34, 5))
        pygame.draw.rect(surface, color, (x, 43, int(34 * ratio), 5))
        if creature.is_fainted():
            # X over fainted
            pygame.draw.line(surface, C_RED, (x, 2), (x+38, 40), 2)
            pygame.draw.line(surface, C_RED, (x+38, 2), (x, 40), 2)


def draw_opponent_hud(surface, session, assets, font):
    if not session.opponent:
        return
    x0 = SCREEN_W - 235
    # Calculate box height based on known info
    box_h = 58
    if session.opponent.known_team_count:
        box_h += 16
    if getattr(session.opponent, "known_level", False):
        box_h += 16
    opp_bg = pygame.Surface((240, box_h), pygame.SRCALPHA)
    opp_bg.fill((0, 0, 0, 100))
    surface.blit(opp_bg, (x0 - 5, 0))
    # faccia rival presa dalla ROM
    face = assets.get_trainer_face(session.opponent.character_id)
    if face:
        surface.blit(face, (x0, 3))
        x0t = x0 + 52
    else:
        x0t = x0
    opp_char = session.characters.get(session.opponent.character_id, {})
    name = opp_char.get("name", "Rival")
    lbl = font.render(f"Rival: {name}", True, C_WHITE)
    surface.blit(lbl, (x0t, 3))
    if session.opponent.known_starter:
        sp = session.opponent.starter_species
        sprite = assets.get_creature(sp, (32, 32))
        surface.blit(sprite, (x0t, 18))
        sn = font.render(session.rom.read_species_name(sp), True, C_WHITE)
        surface.blit(sn, (x0t + 35, 24))
    else:
        surface.blit(font.render("Starter: ??", True, C_GREY), (x0t, 22))
    if session.opponent.known_items:
        surface.blit(font.render("Items: Potions", True, C_WHITE), (x0t, 40))
    else:
        surface.blit(font.render("Items: ??", True, C_GREY), (x0t, 40))
    y_off = 56
    if session.opponent.known_team_count:
        tc = len(session.opponent.team)
        surface.blit(font.render(f"Team: {tc} creatures", True, C_WHITE), (x0t, y_off))
        y_off += 16
    if getattr(session.opponent, "known_level", False):
        max_lv = max(c.level for c in session.opponent.team)
        surface.blit(font.render(f"Max Lv: {max_lv}", True, C_WHITE), (x0t, y_off))


def draw_hud_bar(surface, session, font):
    hud_y = VIEW_TILES_Y * TILE_SIZE
    pygame.draw.rect(surface, C_PANEL, (0, hud_y, SCREEN_W, HUD_H))
    if not session.player:
        return
    active = session.player.active_creature()
    if active:
        t = font.render(f"{active.name} Lv{active.level} HP:{active.hp}/{active.max_hp}", True, C_WHITE)
        surface.blit(t, (10, hud_y + 5))
    inv = session.player.inventory
    itxt = f"Balls:{inv.items.get('pokeball',0)} Potions:{inv.items.get('potion',0)}"
    if inv.has_item("old_rod"): itxt += " Rod:Y"
    hms = []
    if inv.has_hm("cut"): hms.append("CUT")
    if inv.has_hm("surf"): hms.append("SURF")
    if hms: itxt += f" HM:{','.join(hms)}"
    surface.blit(font.render(itxt, True, C_WHITE), (10, hud_y + 25))
    surface.blit(font.render(f"({session.player.x},{session.player.y})", True, C_GREY), (10, hud_y + 45))
    surface.blit(font.render("Arrows:Move Z:Talk X:Fish I:Inv ESC:Quit", True, C_GREY), (10, hud_y + 70))

def draw_rumor_hud(surface, font, rumors):
    """Draw collected rumors in top-right corner."""
    if not rumors:
        return
    max_display = 3  # show last 3 rumors
    recent = rumors[-max_display:]
    box_w = 280
    box_h = 20 + len(recent) * 18
    box_x = SCREEN_W - box_w - 5
    box_y = 60
    s = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    s.fill((0, 0, 0, 160))
    surface.blit(s, (box_x, box_y))
    header = font.render("RIVAL INTEL", True, (255, 200, 50))
    surface.blit(header, (box_x + 5, box_y + 2))
    for i, r in enumerate(recent):
        # Strip "Rumor: " prefix
        txt = r.replace("Rumor: ", "").replace("Rumor:", "")
        if len(txt) > 35:
            txt = txt[:33] + ".."
        line = font.render(f"• {txt}", True, (200, 200, 200))
        surface.blit(line, (box_x + 5, box_y + 20 + i * 18))


def draw_battle(surface, session, assets, font, b_cur, m_cur):
    surface.fill(C_DARK)
    battle = session.battle
    if not battle:
        return
    is_final = session.state == "FINAL_BATTLE"
    if is_final:
        t = font.render("=== FINAL BATTLE ===", True, C_HIGHLIGHT)
        surface.blit(t, (SCREEN_W//2 - t.get_width()//2, 5))
    # Enemy
    es = assets.get_creature(battle.enemy.species_id, (96, 96))
    surface.blit(es, (SCREEN_W - 150, 30))
    surface.blit(font.render(f"{battle.enemy.name} Lv{battle.enemy.level}", True, C_WHITE), (SCREEN_W - 300, 35))
    pygame.draw.rect(surface, C_RED, (SCREEN_W - 300, 55, 130, 8))
    er = max(0, battle.enemy.hp / battle.enemy.max_hp)
    pygame.draw.rect(surface, C_GREEN, (SCREEN_W - 300, 55, int(130*er), 8))
    surface.blit(font.render(f"{battle.enemy.hp}/{battle.enemy.max_hp}", True, C_GREY), (SCREEN_W - 300, 66))
    # Player
    ps = assets.get_creature(battle.player.species_id, (96, 96))
    surface.blit(ps, (50, SCREEN_H - 300))
    surface.blit(font.render(f"{battle.player.name} Lv{battle.player.level}", True, C_WHITE), (40, SCREEN_H - 320))
    pygame.draw.rect(surface, C_RED, (40, SCREEN_H - 200, 130, 8))
    pr = max(0, battle.player.hp / battle.player.max_hp)
    pygame.draw.rect(surface, C_GREEN, (40, SCREEN_H - 200, int(130*pr), 8))
    surface.blit(font.render(f"{battle.player.hp}/{battle.player.max_hp}", True, C_GREY), (40, SCREEN_H - 189))
    # Menu
    my = SCREEN_H - 140
    pygame.draw.rect(surface, C_PANEL, (0, my, SCREEN_W, 140))
    if is_final:
        actions = ["FIGHT", "POTION"]
    else:
        actions = ["FIGHT", "CAPTURE", "POTION", "FLEE"]
    for i, a in enumerate(actions):
        c = C_HIGHLIGHT if i == b_cur else C_WHITE
        surface.blit(font.render(a, True, c), (20 + i * 150, my + 8))
    if b_cur == 0 and battle.player.moves:
        for j, mv in enumerate(battle.player.moves):
            c = C_HIGHLIGHT if j == m_cur else C_WHITE
            surface.blit(font.render(f"{j+1}.{mv.name} P:{mv.power}", True, c), (20+j*148, my+32))
    for idx, msg in enumerate(battle.log[-3:]):
        surface.blit(font.render(msg, True, C_GREY), (20, my + 60 + idx * 17))
    # Sandstorm battle weather effect
    if session.current_map_key in ("rock_desert", "rock_desert_arena", "rock_desert_shelter"):
        try:
            import random
            sandstorm = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            for _ in range(25):
                x = random.randint(0, SCREEN_W)
                y = random.randint(0, SCREEN_H)
                size = random.randint(2, 6)
                alpha = random.randint(40, 100)
                pygame.draw.rect(sandstorm, (210, 180, 120, alpha), (x, y, size, size))
            surface.blit(sandstorm, (0, 0))
        except Exception:
            pass


def draw_inventory(surface, session, font):
    ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 190))
    surface.blit(ov, (0, 0))
    surface.blit(font.render("=== INVENTORY (I to close) ===", True, C_HIGHLIGHT), (20, 15))
    y = 45
    inv = session.player.inventory
    surface.blit(font.render("ITEMS:", True, C_WHITE), (20, y)); y += 20
    for it, cnt in inv.items.items():
        surface.blit(font.render(f"  {it}: x{cnt}", True, C_WHITE), (20, y)); y += 18
    y += 10
    surface.blit(font.render("KEY ITEMS:", True, C_WHITE), (20, y)); y += 20
    for ki in inv.key_items:
        surface.blit(font.render(f"  {ki}", True, C_WHITE), (20, y)); y += 18
    y += 10
    surface.blit(font.render("HMs:", True, C_WHITE), (20, y)); y += 20
    for hm in inv.hms_obtained:
        taught_to = [c.name for c in session.player.team if (hm == "cut" and c.can_cut) or (hm == "surf" and c.can_surf)]
        status = f" -> {taught_to[0]}" if taught_to else " [T to teach]"
        surface.blit(font.render(f"  {hm.upper()}{status}", True, C_WHITE), (20, y)); y += 18
    y += 15
    surface.blit(font.render("TEAM:", True, C_WHITE), (20, y)); y += 20
    for c in session.player.team:
        st = "FAINTED" if c.is_fainted() else "OK"
        surface.blit(font.render(f"  {c.name} Lv{c.level} HP:{c.hp}/{c.max_hp} [{st}]", True, C_WHITE), (20, y)); y += 18


def draw_hm_teach_menu(surface, session, font, hm_name, cursor):
    ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 190))
    surface.blit(ov, (0, 0))
    title = f"Teach {hm_name.upper()} to whom?"
    surface.blit(font.render(title, True, C_HIGHLIGHT), (SCREEN_W//2 - 80, 20))
    y = 55
    team = session.player.team
    for i, c in enumerate(team):
        prefix = "> " if i == cursor else "  "
        st = "FAINTED" if c.is_fainted() else f"HP:{c.hp}/{c.max_hp}"
        can_learn = True
        if hm_name == "cut" and c.can_cut:
            can_learn = False
            st += " [already knows]"
        elif hm_name == "surf" and c.can_surf:
            can_learn = False
            st += " [already knows]"
        elif hm_name == "rock_smash" and getattr(c, 'can_rock_smash', False):
            can_learn = False
            st += " [already knows]"
        elif hm_name == "strength" and getattr(c, 'can_strength', False):
            can_learn = False
            st += " [already knows]"
        color = C_HIGHLIGHT if i == cursor else C_WHITE
        surface.blit(font.render(f"{prefix}{c.name} Lv{c.level} {st}", True, color), (30, y))
        y += 22
    surface.blit(font.render("Z: confirm  X: cancel", True, C_WHITE), (30, y + 10))


def draw_dialogue(surface, text, font, speaker=None):
    bh = 72
    by = SCREEN_H - bh - 5
    box = pygame.Rect(5, by, SCREEN_W - 10, bh)
    pygame.draw.rect(surface, C_PANEL, box)
    pygame.draw.rect(surface, C_WHITE, box, 2)
    yo = 6
    if speaker:
        surface.blit(font.render(speaker, True, C_HIGHLIGHT), (12, by + yo)); yo += 17
    words = text.split()
    lines, cur = [], ""
    for w in words:
        t = cur + " " + w if cur else w
        if font.size(t)[0] < SCREEN_W - 30:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    for i, l in enumerate(lines[:3]):
        surface.blit(font.render(l, True, C_WHITE), (12, by + yo + i * 17))


def draw_char_select(surface, font, characters, assets, cursor, char_ids):
    surface.fill(C_BG)
    surface.blit(font.render("CHOOSE YOUR CHARACTER", True, C_HIGHLIGHT),
                (SCREEN_W//2 - 100, 15))
    for i, cid in enumerate(char_ids):
        ch = characters[cid]
        y = 55 + i * 130
        color = C_HIGHLIGHT if i == cursor else C_WHITE
        # player sprite
        prefix = ch.get("sprite_prefix", "player")
        frame = None
        if prefix.startswith("player_"):
            assets.load_player(prefix)
            frame = assets.player_frame(prefix, "down", 0)
        if not frame:
            frame = assets.get_npc_sprite(prefix)
            if not frame and hasattr(assets, '_load_npc'):
                assets._load_npc()
                frame = assets.get_npc_sprite(prefix)
        if frame:
            surface.blit(frame, (25, y - 5))
        # name
        surface.blit(font.render(ch["name"], True, color), (75, y + 5))
        # starters
        for j, st in enumerate(ch["starter_options"]):
            sp = st["species"]
            spr = assets.get_creature(sp, (48, 48))
            surface.blit(spr, (200 + j * 90, y - 5))
            nm = font.render(f"#{sp}", True, C_GREY)
            surface.blit(nm, (210 + j * 90, y + 45))
    surface.blit(font.render("Up/Down + Enter", True, C_GREY), (SCREEN_W//2 - 60, SCREEN_H - 25))


def draw_starter_select(surface, font, characters, char_id, assets, rom, cursor):
    surface.fill(C_BG)
    ch = characters[char_id]
    surface.blit(font.render(f"{ch['name']} - CHOOSE STARTER", True, C_HIGHLIGHT),
                (SCREEN_W//2 - 90, 15))
    starters = ch["starter_options"]
    for i, st in enumerate(starters):
        sp = st["species"]
        y = 70 + i * 180
        color = C_HIGHLIGHT if i == cursor else C_WHITE
        spr = assets.get_creature(sp, (96, 96))
        surface.blit(spr, (SCREEN_W//2 - 48, y))
        name = rom.read_species_name(sp)
        surface.blit(font.render(name, True, color), (SCREEN_W//2 - 30, y + 100))
        if i == cursor:
            surface.blit(font.render("> SELECT <", True, C_HIGHLIGHT),
                        (SCREEN_W//2 - 35, y + 118))
    surface.blit(font.render("Up/Down + Enter | Backspace=Back", True, C_GREY),
                (SCREEN_W//2 - 120, SCREEN_H - 25))


def draw_mode_select(surface, font, cursor):
    surface.fill(C_BG)
    surface.blit(font.render("THE FINAL POKEBATTLE", True, C_HIGHLIGHT),
                (SCREEN_W//2 - 110, 30))
    surface.blit(font.render("Scegli modalita", True, C_WHITE),
                (SCREEN_W//2 - 70, 60))
    modes = [("ONLINE", "Gioca online"), ("OFFLINE (Campagna)", "Avventura offline")]
    for i, (name, desc) in enumerate(modes):
        y = 120 + i * 70
        color = C_HIGHLIGHT if i == cursor else C_WHITE
        marker = "> " if i == cursor else "  "
        surface.blit(font.render(f"{marker}{name}", True, color),
                    (SCREEN_W//2 - 90, y))
        surface.blit(font.render(desc, True, C_GREY),
                    (SCREEN_W//2 - 90, y + 20))
    surface.blit(font.render("Up/Down + Enter", True, C_GREY),
                (SCREEN_W//2 - 70, SCREEN_H - 25))

def draw_timer(surface, font, seconds):
    m = int(seconds) // 60
    s = int(seconds) % 60
    txt = f"{m:01d}:{s:02d}"
    color = C_WHITE if seconds > 30 else C_RED
    # top center
    bg = pygame.Surface((80, 24), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 120))
    surface.blit(bg, (SCREEN_W//2 - 40, 2))
    lbl = font.render(txt, True, color)
    surface.blit(lbl, (SCREEN_W//2 - lbl.get_width()//2, 7))

def draw_map_select(surface, font, available_maps, cursor):
    surface.fill(C_BG)
    surface.blit(font.render("SELECT MAP", True, C_HIGHLIGHT),
                (SCREEN_W//2 - 45, 15))
    for i, mp in enumerate(available_maps):
        y = 70 + i * 60
        color = C_HIGHLIGHT if i == cursor else C_WHITE
        marker = "> " if i == cursor else "  "
        mp_name = mp["name"]
        surface.blit(font.render(f"{marker}{mp_name}", True, color),
                    (SCREEN_W//2 - 100, y))
        mp_desc = mp["desc"]
        surface.blit(font.render(f"    {mp_desc}", True, C_GREY),
                    (SCREEN_W//2 - 100, y + 18))
    surface.blit(font.render("Up/Down + Enter | Backspace=Back", True, C_GREY),
                (SCREEN_W//2 - 120, SCREEN_H - 25))

# ---------- Main ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="The Final Battle")
    parser.add_argument("--rom", default=None, help="Path to GBA ROM (auto-detected if not specified)")
    args = parser.parse_args()

    # Auto-detect ROM if not specified
    if not args.rom:
        import glob as _glob
        roms = _glob.glob(os.path.join(BASE_DIR, '*.gba'))
        if roms:
            args.rom = roms[0]
        else:
            print("ERROR: No .gba ROM found. Place a ROM in the project root or use --rom path/to/rom.gba")
            sys.exit(1)

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("The Final Battle")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 14)

    session = GameSession()
    session.load_data(rom_path=args.rom)
    extractor = SpriteExtractor(args.rom)
    generate_assets(args.rom)
    assets = Assets(extractor)
    characters = session.characters

    # Blue is not playable at first: he is the fixed rival of the forest map,
    # unlockable as a playable character only after defeating him.
    def refresh_chars():
        return [cid for cid in characters
                if cid not in ("blue", "brock") or cid in session.unlocked]

    char_ids = refresh_chars()
    session.state = "MODE_SELECT"

    # State
    mode_cursor = 0  # 0=Online, 1=Offline
    char_cursor = 0
    starter_cursor = 0
    map_cursor = 0
    available_maps = [
        {"key": "darkwood", "name": "Darkwood Forest", "desc": "Dense forest with cave, river and arena"},
        {"key": "rock_desert", "name": "Rock Desert", "desc": "Mountain shelter, rock maze, arena and Dragon Cave"},
    ]
    battle_cursor = 0
    move_cursor = 0
    selected_char = None
    show_inv = False
    dialogue_text = None
    dialogue_speaker = None
    collected_rumors = []
    dialogue_timer = 0
    pending_hm = None
    hm_cursor = 0
    camera = None
    walker = SmoothWalker()
    pending_encounter = None
    pending_final = False
    surf_transition = None  # {"type": "mount"/"dismount", "dir": ..., "ticks": ...}
    rock_break_anim = None  # {"x":, "y":, "frame": 0-3, "ticks": 0}

    # Input buffer for held-key movement
    move_request = (0, 0)

    running = True
    while running:
        clock.tick(FPS)

        # --- events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if show_inv:
                        show_inv = False
                    else:
                        running = False

                elif session.state == "MODE_SELECT":
                    if event.key in (pygame.K_UP, pygame.K_LEFT):
                        mode_cursor = (mode_cursor - 1) % 2
                    elif event.key in (pygame.K_DOWN, pygame.K_RIGHT):
                        mode_cursor = (mode_cursor + 1) % 2
                    elif event.key == pygame.K_RETURN:
                        if mode_cursor == 0:
                            dialogue_text = "Online non disponibile"
                            dialogue_speaker = "Sistema"
                            dialogue_timer = 120
                        else:
                            session.mode = "offline"
                            char_ids = refresh_chars()
                            char_cursor = 0
                            session.state = "CHARACTER_SELECT"
                    elif event.key == pygame.K_ESCAPE:
                        running = False

                elif session.state == "CHARACTER_SELECT":
                    if event.key in (pygame.K_UP, pygame.K_LEFT):
                        char_cursor = (char_cursor - 1) % len(char_ids)
                    elif event.key in (pygame.K_DOWN, pygame.K_RIGHT):
                        char_cursor = (char_cursor + 1) % len(char_ids)
                    elif event.key == pygame.K_RETURN:
                        selected_char = char_ids[char_cursor]
                        starter_cursor = 0
                        session.state = "STARTER_SELECT"
                    elif event.key == pygame.K_BACKSPACE:
                        session.state = "MODE_SELECT"

                elif session.state == "STARTER_SELECT":
                    sts = characters[selected_char]["starter_options"]
                    if event.key in (pygame.K_UP, pygame.K_LEFT):
                        starter_cursor = (starter_cursor - 1) % len(sts)
                    elif event.key in (pygame.K_DOWN, pygame.K_RIGHT):
                        starter_cursor = (starter_cursor + 1) % len(sts)
                    elif event.key == pygame.K_RETURN:
                        map_cursor = 0
                        session.state = "MAP_SELECT"

                elif session.state == "MAP_SELECT":
                    if event.key in (pygame.K_UP, pygame.K_LEFT):
                        map_cursor = (map_cursor - 1) % len(available_maps)
                    elif event.key in (pygame.K_DOWN, pygame.K_RIGHT):
                        map_cursor = (map_cursor + 1) % len(available_maps)
                    elif event.key == pygame.K_RETURN:
                        sts = characters[selected_char]["starter_options"]
                        sp = sts[starter_cursor]["species"]
                        chosen_map = available_maps[map_cursor]["key"]
                        session.start_game(selected_char, sp, map_key=chosen_map)
                        m = session.get_current_map()
                        camera = Camera(m["width"], m["height"])
                        extractor.extract_creature_sprite(sp)
                        pf = characters[selected_char].get("sprite_prefix", "player")
                        assets.load_player(pf)
                        map_name = available_maps[map_cursor]["name"]
                        dialogue_text = f"Adventure begins! Map: {map_name}"
                        dialogue_timer = 100
                    elif event.key == pygame.K_BACKSPACE:
                        session.state = "STARTER_SELECT"

                elif session.state in ("VICTORY", "GAME_OVER"):
                    # Return to character select to start another run.
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        char_ids = refresh_chars()
                        char_cursor = 0
                        selected_char = None
                        session.state = "CHARACTER_SELECT"








                    elif event.key == pygame.K_BACKSPACE:
                        session.state = "CHARACTER_SELECT"

                elif session.state == "EXPLORING":
                    if show_inv:
                        if event.key == pygame.K_i:
                            show_inv = False
                        elif event.key == pygame.K_t:
                            inv = session.player.inventory
                            for hm in inv.hms_obtained:
                                has_it = [c for c in session.player.team if
                                          (hm == "cut" and c.can_cut) or
                                          (hm == "surf" and c.can_surf) or
                                          (hm == "rock_smash" and getattr(c, 'can_rock_smash', False)) or
                                          (hm == "strength" and getattr(c, 'can_strength', False))]
                                if not has_it and session.player.team:
                                    pending_hm = hm
                                    hm_cursor = 0
                                    session.state = "TEACH_HM"
                                    show_inv = False
                                    break
                        continue
                    if dialogue_text:
                        dialogue_text = None; dialogue_timer = 0
                        continue
                    if event.key == pygame.K_i:
                        show_inv = True
                    elif event.key == pygame.K_z:
                        r = session.interact()
                        if r and r.get("npc"):
                            dialogue_text = r["dialogue"]
                            dialogue_speaker = r.get("name")
                            if r.get("received"):
                                dialogue_text += f" [Got: {r['received']}]"
                            if r.get("teach_hm"):
                                pending_hm = r["teach_hm"]
                                hm_cursor = 0
                                session.state = "TEACH_HM"
                            dialogue_timer = 200
                        elif r and r.get("sign"):
                            dialogue_text = r["text"]; dialogue_speaker = "Sign"
                            dialogue_timer = 150
                            if r["text"].lower().startswith("rumor:") and r["text"] not in collected_rumors:
                                collected_rumors.append(r["text"])
                            if r.get("reveal") and session.opponent:
                                session.opponent.reveal(r["reveal"])
                    elif event.key == pygame.K_x:
                        r = session.try_fish()
                        if r.get("encounter"):
                            w = r["wild_creature"]
                            extractor.extract_creature_sprite(w.species_id)
                            dialogue_text = f"Hooked a {w.name} Lv{w.level}!"
                            dialogue_timer = 90; battle_cursor = 0; move_cursor = 0
                        elif r.get("fail"):
                            msgs = {"no_rod": "No fishing rod!", "no_water": "No water here!",
                                    "nothing_bites": "Nothing's biting..."}
                            dialogue_text = msgs.get(r["reason"], "Can't fish here.")
                            dialogue_timer = 60

                elif session.state == "TEACH_HM":
                    if dialogue_text:
                        dialogue_text = None; dialogue_timer = 0
                        continue
                    team = session.player.team
                    if not team:
                        session.state = "EXPLORING"
                        continue
                    if event.key in (pygame.K_UP, pygame.K_w):
                        hm_cursor = (hm_cursor - 1) % len(team)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        hm_cursor = (hm_cursor + 1) % len(team)
                    elif event.key in (pygame.K_z, pygame.K_RETURN):
                        chosen = team[hm_cursor]
                        ok = chosen.teach_hm(pending_hm, rom=session.rom)
                        if ok:
                            dialogue_text = f"Taught {pending_hm.upper()} to {chosen.name}!"
                        else:
                            dialogue_text = f"{chosen.name} can't learn {pending_hm.upper()}!"
                        dialogue_speaker = "System"
                        dialogue_timer = 120
                        pending_hm = None
                        session.state = "EXPLORING"
                    elif event.key in (pygame.K_x, pygame.K_ESCAPE):
                        pending_hm = None
                        session.state = "EXPLORING"

                elif session.state in ("BATTLE", "FINAL_BATTLE"):
                    if dialogue_text:
                        dialogue_text = None; dialogue_timer = 0
                        continue
                    is_final = session.state == "FINAL_BATTLE"
                    n_act = 2 if is_final else 4
                    if event.key in (pygame.K_UP,):
                        battle_cursor = (battle_cursor - 1) % n_act; move_cursor = 0
                    elif event.key in (pygame.K_DOWN,):
                        battle_cursor = (battle_cursor + 1) % n_act; move_cursor = 0
                    elif event.key == pygame.K_LEFT:
                        if battle_cursor == 0 and session.battle.player.moves:
                            move_cursor = (move_cursor - 1) % len(session.battle.player.moves)
                        else:
                            battle_cursor = (battle_cursor - 1) % n_act; move_cursor = 0
                    elif event.key == pygame.K_RIGHT:
                        if battle_cursor == 0 and session.battle.player.moves:
                            move_cursor = (move_cursor + 1) % len(session.battle.player.moves)
                        else:
                            battle_cursor = (battle_cursor + 1) % n_act; move_cursor = 0
                    elif event.key == pygame.K_RETURN:
                        if is_final:
                            act = "attack" if battle_cursor == 0 else "potion"
                        else:
                            act = ["attack", "capture", "potion", "flee"][battle_cursor]
                        msgs = session.battle_action(act, move_cursor if act == "attack" else 0)
                        if msgs:
                            dialogue_text = " | ".join(msgs[-2:]); dialogue_timer = 110
                    elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                        mi = min(event.key - pygame.K_1, len(session.battle.player.moves)-1)
                        move_cursor = mi
                        if battle_cursor == 0:
                            msgs = session.battle_action("attack", mi)
                            if msgs:
                                dialogue_text = " | ".join(msgs[-2:]); dialogue_timer = 110

        # --- timer & IA update (3 min + centro) ---
        if session.state == "EXPLORING" and session.player:
            dt = 1.0 / FPS
            res = session.update(dt)
            # session.update may have switched to FINAL_BATTLE and repositioned player
            if res is not None or session.state == "FINAL_BATTLE":
                if session.state == "FINAL_BATTLE":
                    m = session.get_current_map()
                    camera = Camera(m["width"], m["height"])
                    walker.reset()
                    assets.map_bg = None
                    dialogue_text = "Centro raggiunto! Battaglia finale!"
                    dialogue_timer = 120
                    battle_cursor = 0; move_cursor = 0
                    pending_final = False
                    pending_encounter = None

        # --- smooth walk logic ---
        if session.state == "EXPLORING" and not show_inv and not dialogue_text:
            step_done = walker.update()
            # A surf mount/dismount transition lasts exactly one walk step.
            if step_done:
                surf_transition = None
            # Pending encounter triggers AFTER walk animation completes
            if step_done and pending_encounter:
                w = pending_encounter
                extractor.extract_creature_sprite(w.species_id)
                dialogue_text = f"Wild {w.name} Lv{w.level} appeared!"
                dialogue_timer = 90; battle_cursor = 0; move_cursor = 0
                pending_encounter = None
            elif step_done and pending_final:
                dialogue_text = "RIVAL BATTLE! Get ready!"
                dialogue_timer = 120; battle_cursor = 0; move_cursor = 0
                pending_final = False
            # If not currently walking (or in a surf transition), check for held keys
            if not walker.walking and not surf_transition:
                keys = pygame.key.get_pressed()
                dx, dy = 0, 0
                if keys[pygame.K_UP]: dy = -1
                elif keys[pygame.K_DOWN]: dy = 1
                elif keys[pygame.K_LEFT]: dx = -1
                elif keys[pygame.K_RIGHT]: dx = 1
                if dx != 0 or dy != 0:
                    result = session.move_player(dx, dy)
                    if result and not result.get("blocked"):
                        if result.get("portal"):
                            m = session.get_current_map()
                            camera = Camera(m["width"], m["height"])
                            walker.reset()
                            assets.map_bg = None
                            dest = result.get("dest_map", "?")
                            dialogue_text = f"Entered {dest}!"
                            dialogue_timer = 60
                        else:
                            if result.get("surf_mount") or result.get("surf_dismount"):
                                # Getting on/off the Pokemon: glide onto the
                                # tile while showing the boarding frame for the
                                # whole step.
                                surf_transition = {
                                    "type": "mount" if result.get("surf_mount") else "dismount",
                                    "dir": session.player.direction,
                                }
                            walker.start_step(dx, dy)
                            if result.get("encounter"):
                                pending_encounter = result["wild_creature"]
                            elif result.get("final_battle"):
                                pending_final = True
                            elif result.get("cut"):
                                dialogue_text = "CUT! Tree cleared."
                                dialogue_timer = 50
                            elif result.get("rock_smash"):
                                # Start rock break animation
                                rx, ry = result.get("rock_x", 0), result.get("rock_y", 0)
                                rock_break_anim = {"x": rx, "y": ry, "frame": 0, "ticks": 0}
                                dialogue_text = "Crack! The rock shattered!"
                                dialogue_timer = 50
                            elif result.get("pickup"):
                                item_name = result.get("item_name", "item")
                                dialogue_text = f"Found {item_name}!"
                                dialogue_timer = 90
                    elif result and result.get("blocked"):
                        reason = result.get("reason", "")
                        if reason == "need_surf":
                            dialogue_text = "Need SURF to cross water."
                            dialogue_timer = 50
                        elif reason == "need_cut":
                            dialogue_text = "Need CUT for this tree."
                            dialogue_timer = 50
                        elif reason == "need_rock_smash":
                            dialogue_text = "Need Rock Smash for this boulder!"
                            dialogue_timer = 50
                        elif reason == "need_strength":
                            dialogue_text = "Need Strength to push this!"
                            dialogue_timer = 50
                        elif reason == "sign":
                            dialogue_text = "Press Z to read the sign."
                            dialogue_timer = 40
                        if dx > 0: session.player.direction = "right"
                        elif dx < 0: session.player.direction = "left"
                        elif dy > 0: session.player.direction = "down"
                        elif dy < 0: session.player.direction = "up"
        else:
            walker.update()

        # --- dialogue timer ---
        if dialogue_timer > 0:
            dialogue_timer -= 1
            if dialogue_timer <= 0:
                dialogue_text = None; dialogue_speaker = None

        # --- camera ---
        if camera and session.player:
            if walker.walking:
                ox, oy = walker.get_render_offset()
                ppx = session.player.x * TILE_SIZE - (1 - walker.anim_tick/WALK_FRAMES) * walker.dir_x * TILE_SIZE
                ppy = session.player.y * TILE_SIZE - (1 - walker.anim_tick/WALK_FRAMES) * walker.dir_y * TILE_SIZE
            else:
                ppx = session.player.x * TILE_SIZE
                ppy = session.player.y * TILE_SIZE
            camera.update(ppx, ppy)

        # --- render ---
        screen.fill(C_BG)

        if session.state == "MODE_SELECT":
            draw_mode_select(screen, font, mode_cursor)
        elif session.state == "CHARACTER_SELECT":
            draw_char_select(screen, font, characters, assets, char_cursor, char_ids)
        elif session.state == "STARTER_SELECT":
            draw_starter_select(screen, font, characters, selected_char, assets, session.rom, starter_cursor)
        elif session.state == "MAP_SELECT":
            draw_map_select(screen, font, available_maps, map_cursor)
        elif session.state == "EXPLORING":
            draw_map(screen, session, assets, camera, rock_break_anim)
            draw_npcs(screen, session, assets, camera)
            draw_ai(screen, session, assets, camera)
            draw_player(screen, session, assets, camera, walker, surf_transition)
            draw_team_hud(screen, session, assets, font)
            draw_opponent_hud(screen, session, assets, font)
            draw_timer(screen, font, getattr(session, "timer", 0))
            draw_hud_bar(screen, session, font)
            draw_rumor_hud(screen, font, collected_rumors)
            if show_inv:
                draw_inventory(screen, session, font)
        elif session.state == "TEACH_HM":
            draw_map(screen, session, assets, camera, rock_break_anim)
            draw_npcs(screen, session, assets, camera)
            draw_ai(screen, session, assets, camera)
            draw_player(screen, session, assets, camera, walker, surf_transition)
            draw_team_hud(screen, session, assets, font)
            draw_hm_teach_menu(screen, session, font, pending_hm, hm_cursor)
        elif session.state in ("BATTLE", "FINAL_BATTLE"):
            draw_battle(screen, session, assets, font, battle_cursor, move_cursor)
        elif session.state == "VICTORY":
            screen.fill(C_BG)
            surface = screen
            surface.blit(font.render("=== VICTORY ===", True, C_HIGHLIGHT),
                        (SCREEN_W//2 - 60, SCREEN_H//2 - 20))
            surface.blit(font.render("You defeated your rival!", True, C_WHITE),
                        (SCREEN_W//2 - 80, SCREEN_H//2 + 10))
            y_offset = 40
            for char_id in ("blue", "brock"):
                if char_id in session.unlocked:
                    char_name = session.characters.get(char_id, {}).get("name", char_id.upper())
                    surface.blit(font.render(f"{char_name} unlocked as a playable character!", True, (120, 220, 120)),
                                (SCREEN_W//2 - 160, SCREEN_H//2 + y_offset))
                    y_offset += 20
            surface.blit(font.render("Enter: new game | ESC: exit", True, C_GREY),
                        (SCREEN_W//2 - 100, SCREEN_H//2 + 70))
        elif session.state == "GAME_OVER":
            screen.fill(C_DARK)
            go_txt = font.render("=== GAME OVER ===", True, C_RED)
            screen.blit(go_txt, (SCREEN_W//2 - go_txt.get_width()//2, SCREEN_H//2 - 30))
            sub = font.render("All your creatures fainted!", True, C_WHITE)
            screen.blit(sub, (SCREEN_W//2 - sub.get_width()//2, SCREEN_H//2 + 5))
            hint = font.render("Press ESC to exit", True, C_GREY)
            screen.blit(hint, (SCREEN_W//2 - hint.get_width()//2, SCREEN_H//2 + 35))

        if dialogue_text:
            draw_dialogue(screen, dialogue_text, font, dialogue_speaker)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
