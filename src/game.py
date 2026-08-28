"""
The Final Battle - Core game engine.
Full game loop: character select, spawn, explore, collect, discover, final battle.
All creature/move data read from ROM at runtime.
"""

import json
import os
import random
from rom_reader import RomReader, find_rom

# ---------- paths ----------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
ASSET_DIR = os.path.join(BASE_DIR, "assets")

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r") as f:
        return json.load(f)


# ---------- Move & Creature -------------------------------------------------

class Move:
    def __init__(self, name, power, accuracy=100, element="normal", move_id=0, is_hm=False):
        self.name = name
        self.power = power
        self.accuracy = accuracy
        self.element = element
        self.move_id = move_id
        self.is_hm = is_hm

    def __repr__(self):
        return f"Move({self.name}, pwr={self.power})"


class Creature:
    def __init__(self, species_id, name, element, base_hp, base_atk, base_def,
                 base_spd, level=5, moves=None):
        self.species_id = species_id
        self.name = name
        self.element = element
        self.base_hp = base_hp
        self.base_atk = base_atk
        self.base_def = base_def
        self.base_spd = base_spd
        self.level = level
        self.moves = moves or []
        self.max_hp = self._calc_hp()
        self.hp = self.max_hp
        self.atk = self._calc_stat(base_atk)
        self.defense = self._calc_stat(base_def)
        self.spd = self._calc_stat(base_spd)
        self.can_surf = False
        self.can_cut = False

    def _calc_hp(self):
        return int((self.base_hp * 2 * self.level) / 100) + self.level + 10

    def _calc_stat(self, base):
        return int((base * 2 * self.level) / 100) + 5

    def is_fainted(self):
        return self.hp <= 0

    def take_damage(self, dmg):
        self.hp = max(0, self.hp - dmg)

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    def teach_hm(self, hm_name):
        if hm_name == "cut":
            self.can_cut = True
            if not any(m.name == "CUT" for m in self.moves):
                self.moves.append(Move("CUT", 50, 95, "normal", is_hm=True))
        elif hm_name == "surf":
            self.can_surf = True
            if not any(m.name == "SURF" for m in self.moves):
                self.moves.append(Move("SURF", 90, 100, "water", is_hm=True))

    def __repr__(self):
        return f"{self.name} Lv{self.level} HP={self.hp}/{self.max_hp}"


def make_creature_from_rom(species_id, level, rom_reader):
    """Create Creature from ROM data."""
    species_data = rom_reader.read_species(species_id)
    if species_data is None:
        return Creature(species_id, f"???{species_id}", "normal", 40, 40, 40, 40, level,
                       [Move("TACKLE", 35, 95, "normal")])

    learnset = rom_reader.read_learnset(species_id)
    learnable = [(lv, mid) for lv, mid in learnset if lv <= level]
    learnable.sort(key=lambda x: x[0], reverse=True)

    move_objs = []
    for lv, mid in learnable[:4]:
        move_data = rom_reader.read_battle_move(mid)
        if move_data and move_data["power"] > 0:
            move_objs.append(Move(
                name=move_data["name"], power=move_data["power"],
                accuracy=move_data["accuracy"] if move_data["accuracy"] > 0 else 100,
                element=move_data["element"], move_id=mid
            ))

    if not move_objs:
        for lv, mid in learnable[:4]:
            move_data = rom_reader.read_battle_move(mid)
            if move_data:
                move_objs.append(Move(
                    name=move_data["name"],
                    power=max(move_data["power"], 30),
                    accuracy=move_data["accuracy"] if move_data["accuracy"] > 0 else 100,
                    element=move_data["element"], move_id=mid
                ))
                break
    if not move_objs:
        move_objs = [Move("STRUGGLE", 50, 100, "normal")]

    return Creature(
        species_id=species_id, name=species_data["name"],
        element=species_data["element"],
        base_hp=species_data["base_hp"], base_atk=species_data["base_atk"],
        base_def=species_data["base_def"], base_spd=species_data["base_spd"],
        level=level, moves=move_objs
    )


# ---------- Battle Engine ---------------------------------------------------

class BattleEngine:
    def __init__(self, player_creature, enemy_creature, is_final=False):
        self.player = player_creature
        self.enemy = enemy_creature
        self.log = []
        self.turn = 0
        self.finished = False
        self.result = None
        self.is_final = is_final

    def calc_damage(self, attacker, defender, move):
        if move.accuracy > 0 and random.randint(1, 100) > move.accuracy:
            return 0
        base_dmg = ((2 * attacker.level / 5 + 2) * move.power *
                    attacker.atk / defender.defense) / 50 + 2
        base_dmg *= random.randint(85, 100) / 100.0
        return max(1, int(base_dmg))

    def player_attack(self, move_index):
        if self.finished:
            return []
        self.turn += 1
        messages = []
        move_idx = min(move_index, len(self.player.moves) - 1)
        p_move = self.player.moves[move_idx]

        if self.player.spd >= self.enemy.spd:
            messages += self._do_attack(self.player, self.enemy, p_move)
            if not self.enemy.is_fainted():
                e_move = random.choice(self.enemy.moves)
                messages += self._do_attack(self.enemy, self.player, e_move)
        else:
            e_move = random.choice(self.enemy.moves)
            messages += self._do_attack(self.enemy, self.player, e_move)
            if not self.player.is_fainted():
                messages += self._do_attack(self.player, self.enemy, p_move)

        if self.enemy.is_fainted():
            self.finished = True
            self.result = "win"
            messages.append(f"{self.enemy.name} fainted! You win!")
        elif self.player.is_fainted():
            self.finished = True
            self.result = "lose"
            messages.append(f"{self.player.name} fainted!")

        self.log.extend(messages)
        return messages

    def try_flee(self):
        if self.finished:
            return []
        if self.is_final:
            return ["Can't flee from the final battle!"]
        chance = (self.player.spd * 128 // max(1, self.enemy.spd) + 30) % 256
        if random.randint(0, 255) < chance:
            self.finished = True
            self.result = "fled"
            return ["Got away safely!"]
        e_move = random.choice(self.enemy.moves)
        msgs = ["Could not escape!"]
        msgs += self._do_attack(self.enemy, self.player, e_move)
        if self.player.is_fainted():
            self.finished = True
            self.result = "lose"
            msgs.append(f"{self.player.name} fainted!")
        self.log.extend(msgs)
        return msgs

    def try_capture(self, ball_bonus=1.0):
        if self.finished:
            return []
        if self.is_final:
            return ["Can't capture your rival's creature!"]
        hp_factor = (3 * self.enemy.max_hp - 2 * self.enemy.hp) / (3 * self.enemy.max_hp)
        catch_rate = min(255, int(hp_factor * 200 * ball_bonus))
        if random.randint(0, 255) < catch_rate:
            self.finished = True
            self.result = "captured"
            return [f"Gotcha! {self.enemy.name} was captured!"]
        e_move = random.choice(self.enemy.moves)
        msgs = ["It broke free!"]
        msgs += self._do_attack(self.enemy, self.player, e_move)
        if self.player.is_fainted():
            self.finished = True
            self.result = "lose"
            msgs.append(f"{self.player.name} fainted!")
        self.log.extend(msgs)
        return msgs

    def _do_attack(self, attacker, defender, move):
        dmg = self.calc_damage(attacker, defender, move)
        if dmg == 0:
            return [f"{attacker.name} used {move.name}... but missed!"]
        defender.take_damage(dmg)
        return [f"{attacker.name} used {move.name}! {dmg} dmg to {defender.name}."]


# ---------- Inventory -------------------------------------------------------

class Inventory:
    """Player inventory with items."""
    def __init__(self, starting_items=None):
        self.items = {}  # name -> count
        self.hms_obtained = set()  # "cut", "surf"
        self.key_items = set()     # "old_rod", etc.
        if starting_items:
            for entry in starting_items:
                self.items[entry["item"]] = entry["count"]

    def add_item(self, name, count=1):
        self.items[name] = self.items.get(name, 0) + count

    def use_item(self, name):
        if self.items.get(name, 0) > 0:
            self.items[name] -= 1
            if self.items[name] <= 0:
                del self.items[name]
            return True
        return False

    def has_item(self, name):
        return self.items.get(name, 0) > 0 or name in self.key_items

    def add_key_item(self, name):
        self.key_items.add(name)

    def has_hm(self, hm_name):
        return hm_name in self.hms_obtained

    def obtain_hm(self, hm_name):
        self.hms_obtained.add(hm_name)


# ---------- Opponent State --------------------------------------------------

class OpponentState:
    """Tracks what we know about the AI opponent."""
    def __init__(self, character_id, starter_species, rom):
        self.character_id = character_id
        self.starter_species = starter_species
        self.team = []  # built during game
        # Build opponent team
        self.team.append(make_creature_from_rom(starter_species, 8, rom))
        # Opponent also catches some creatures
        opponent_catches = [41, 23, 58]  # random species for opponent
        for sp in opponent_catches:
            self.team.append(make_creature_from_rom(sp, 7, rom))
        # What the player knows
        self.known_starter = False
        self.known_items = False
        self.known_team_count = False
        self.known_level = False

    def reveal(self, what):
        if what in ("starter", "opponent_type"):
            self.known_starter = True
        elif what in ("items", "opponent_items"):
            self.known_items = True
        elif what in ("team_size", "team_member", "opponent_team"):
            self.known_team_count = True
        elif what == "level":
            self.known_level = True









# ---------- Player State ----------------------------------------------------

class PlayerState:
    def __init__(self, character_id, starter_creature, starting_items=None):
        self.character_id = character_id
        self.team = [starter_creature]
        self.inventory = Inventory(starting_items)
        self.x = 0
        self.y = 0
        self.direction = "down"
        self.steps = 0
        self.walk_frame = 0
        self.surfing = False

    def active_creature(self):
        for c in self.team:
            if not c.is_fainted():
                return c
        return None

    def add_creature(self, creature):
        if len(self.team) < 6:
            self.team.append(creature)
            return True
        return False

    def has_cut(self):
        return any(c.can_cut for c in self.team)

    def has_surf(self):
        return any(c.can_surf for c in self.team)

    def has_rod(self):
        return self.inventory.has_item("old_rod")

    def heal_team(self):
        for c in self.team:
            c.hp = c.max_hp


# ---------- Game Session (state machine) ------------------------------------

class GameSession:
    STATES = ("MODE_SELECT", "TITLE", "CHARACTER_SELECT", "STARTER_SELECT", "MAP_SELECT", "EXPLORING",
              "BATTLE", "FINAL_BATTLE", "INVENTORY", "DIALOGUE", "GAME_OVER", "VICTORY")

    # Centro mappa: punto stabilito al centro dove scatta il teletrasporto/battaglia finale
    CENTER_MAP = "area_central"
    CENTER_POS = (10, 5)  # dentro arena_bounds, dove sta Rival
    TIMER_SECONDS = 180  # 3 minuti

    def __init__(self):
        self.state = "TITLE"
        self.mode = None  # "offline" or "online"
        self.player = None
        self.opponent = None
        self.map_data = None
        self.rom = None
        self.battle = None
        self.seed = None
        self.rng = None
        self.characters = None
        self.current_dialogue = None
        self.npc_gifts_given = set()  # track which NPCs already gave items
        self.cut_tiles_removed = set()  # (x, y) of removed cuttable trees
        self.final_battle_index = 0  # which opponent creature we're fighting
        self.current_map_key = "forest_south"  # default, set in start_game
        self.previous_map_key = None
        self.previous_map_pos = (0, 0)
        self.unlocked = set()  # character ids unlockable by defeating their rival (e.g. "blue")
        # Timer & IA (Blue)
        self.timer = self.TIMER_SECONDS
        self.ai_x = 0
        self.ai_y = 0
        self.ai_map_key = "forest_south"
        self.ai_direction = "down"
        self.ai_tick = 0  # frames since last AI step
        self.ai_speed = 18  # frames per tile (più lento del player)

    def load_data(self, rom_path=None):
        if rom_path is None:
            rom_path = find_rom()
        if rom_path is None:
            raise FileNotFoundError("No .gba ROM found. Use --rom <path>.")
        self.rom = RomReader(rom_path)
        self.map_data = load_json("maps.json")
        self.characters = load_json("characters.json")

    def start_game(self, character_id, starter_species_id, seed=None):
        """Start with chosen character + starter. Random spawn."""
        self.seed = seed if seed is not None else random.randint(0, 99999)
        self.rng = random.Random(self.seed)

        starter = make_creature_from_rom(starter_species_id, 5, self.rom)
        char_data = self.characters[character_id]
        self.player = PlayerState(character_id, starter, char_data.get("starting_items"))

        # Random spawn: 50% forest_south, 50% forest_north
        spawn_maps = ["forest_south", "forest_north"]
        spawn_idx = self.rng.randint(0, 1)
        self.current_map_key = spawn_maps[spawn_idx]
        current = self.map_data[self.current_map_key]
        sp = current["spawn"]
        self.player.x = sp[0]
        self.player.y = sp[1]

        # Blue is the fixed rival of the forest map (not playable at the start).
        opp_char = "blue" if "blue" in self.characters else next(
            c for c in self.characters if c != character_id
        )
        opp_starters = self.characters[opp_char]["starter_options"]
        opp_starter = self.rng.choice(opp_starters)["species"]
        self.opponent = OpponentState(opp_char, opp_starter, self.rom)

        # Timer e IA: IA spawn opposto al player
        self.timer = self.TIMER_SECONDS
        other_map = "forest_north" if self.current_map_key == "forest_south" else "forest_south"
        self.ai_map_key = other_map
        sp_ai = self.map_data[self.ai_map_key]["spawn"]
        self.ai_x, self.ai_y = sp_ai[0], sp_ai[1]
        self.ai_direction = "down"
        self.ai_tick = 0

        self.state = "EXPLORING"















    def get_current_map(self):
        return self.map_data.get(self.current_map_key, {})

    def get_tile_at(self, x, y):
        """Get tile character at position, accounting for cut tiles."""
        if (x, y) in self.cut_tiles_removed:
            return 'd'  # cut tree becomes path
        layout = self.map_data[self.current_map_key]["layout"]
        if 0 <= y < len(layout) and 0 <= x < len(layout[0]):
            return layout[y][x]
        return 'T'  # out of bounds = impassable

    @staticmethod
    def _nearest_walkable_col(layout, row, walkable, x):
        """Column on `row` (a walkable tile) closest to x."""
        row_str = layout[row]
        best, best_d = None, len(row_str) + 1
        for c in range(len(row_str)):
            if row_str[c] in walkable and abs(c - x) < best_d:
                best, best_d = c, abs(c - x)
        return best if best is not None else min(max(x, 0), len(row_str) - 1)

    @staticmethod
    def _nearest_walkable_row(layout, col, walkable, y):
        """Row in column `col` (a walkable tile) closest to y."""
        best, best_d = None, len(layout) + 1
        for r in range(len(layout)):
            if col < len(layout[r]) and layout[r][col] in walkable and abs(r - y) < best_d:
                best, best_d = r, abs(r - y)
        return best if best is not None else min(max(y, 0), len(layout) - 1)

    def _edge_landing(self, direction, dest_layout, dest_walk):
        """Position the player on a walkable tile in the destination map.

        Only allows crossing an edge connection when the player is standing on
        a road/path tile at that edge (so the whole forest border doesn't act as
        a teleporter). Returns True when the player has been placed, else False.
        """
        src = self.map_data[self.current_map_key]["layout"]
        px, py = self.player.x, self.player.y
        # Only the road/path at the edge is a valid transition, not the whole
        # forest border (grass '.'-tiles etc.).
        if src[py][px] not in ("d",):
            return False
        if direction == "north":
            dest_row = len(dest_layout) - 1
            self.player.x = self._nearest_walkable_col(dest_layout, dest_row, dest_walk, px)
            self.player.y = dest_row
        elif direction == "south":
            dest_row = 0
            self.player.x = self._nearest_walkable_col(dest_layout, dest_row, dest_walk, px)
            self.player.y = dest_row
        elif direction == "east":
            dest_col = 0
            self.player.y = self._nearest_walkable_row(dest_layout, dest_col, dest_walk, py)
            self.player.x = dest_col
        elif direction == "west":
            dest_col = len(dest_layout[0]) - 1
            self.player.y = self._nearest_walkable_row(dest_layout, dest_col, dest_walk, py)
            self.player.x = dest_col
        return True

    def move_player(self, dx, dy):
        if self.state != "EXPLORING":
            return None

        # Game over if all creatures fainted
        if self.player.active_creature() is None:
            self.state = "GAME_OVER"
            return {"game_over": True}

        new_x = self.player.x + dx
        new_y = self.player.y + dy
        current_map = self.get_current_map()
        layout = current_map["layout"]

        if new_y < 0 or new_y >= len(layout) or new_x < 0 or new_x >= len(layout[0]):
            # Check edge_connections for map transition
            edges = current_map.get("edge_connections", {})
            direction = None
            if new_y < 0: direction = "north"
            elif new_y >= len(layout): direction = "south"
            elif new_x < 0: direction = "west"
            elif new_x >= len(layout[0]): direction = "east"
            dest_map_key = edges.get(direction)
            if dest_map_key and dest_map_key in self.map_data:
                dest_layout = self.map_data[dest_map_key]["layout"]
                dest_walk = self.map_data[dest_map_key].get("walkable_tiles", [])
                # Only transition from the road/path at the edge and land on a
                # walkable tile in the destination (avoids warping in off the
                # forest edge straight into trees/water).
                if self._edge_landing(direction, dest_layout, dest_walk):
                    self.previous_map_key = self.current_map_key
                    self.previous_map_pos = (self.player.x, self.player.y)
                    self.current_map_key = dest_map_key
                    return {"moved": True, "portal": True, "dest_map": dest_map_key}
            return {"blocked": True}

        # NPC collision - can't walk through NPCs
        for npc in current_map.get("npcs", []):
            if npc["x"] == new_x and npc["y"] == new_y:
                return {"blocked": True, "reason": "npc"}

        # Sign collision - can't walk through signs
        for sign in current_map.get("signs", []):
            if sign["x"] == new_x and sign["y"] == new_y:
                return {"blocked": True, "reason": "sign"}

        tile = self.get_tile_at(new_x, new_y)
        walkable = current_map.get("walkable_tiles", [])

        # Update direction first so the surf mount/dismount frame faces the
        # right way before we decide whether this step changes surf state.
        if dx > 0:
            self.player.direction = "right"
        elif dx < 0:
            self.player.direction = "left"
        elif dy > 0:
            self.player.direction = "down"
        elif dy < 0:
            self.player.direction = "up"

        surf = {"mount": False, "dismount": False}

        # Water requires SURF and mounts the Pokemon on first contact
        if tile == 'w':
            if not self.player.has_surf():
                return {"blocked": True, "reason": "need_surf"}
            if not self.player.surfing:
                self.player.surfing = True
                surf["mount"] = True  # play get-on animation

        # Cuttable tree requires CUT
        elif tile == 'C':
            if self.player.has_cut():
                self.cut_tiles_removed.add((new_x, new_y))
                return {"cut": True, "x": new_x, "y": new_y}
            else:
                return {"blocked": True, "reason": "need_cut"}

        elif tile not in walkable:
            return {"blocked": True}

        else:
            # Stepping from water onto land -> get off the Pokemon
            if self.player.surfing:
                self.player.surfing = False
                surf["dismount"] = True

        self.player.x = new_x
        self.player.y = new_y
        self.player.steps += 1
        self.player.walk_frame += 1

        # Check for portal/map transition
        portals = current_map.get("portals", [])
        for portal in portals:
            if portal["x"] == new_x and portal["y"] == new_y:
                self.previous_map_key = self.current_map_key
                self.previous_map_pos = (self.player.x, self.player.y)
                self.current_map_key = portal["dest_map"]
                self.player.x = portal["dest_x"]
                self.player.y = portal["dest_y"]
                return {"moved": True, "portal": True, "dest_map": portal["dest_map"]}

        # Check dynamic_exit (house interior -> return to previous map)
        dyn_exit = current_map.get("dynamic_exit")
        if dyn_exit and new_x == dyn_exit["x"] and new_y == dyn_exit["y"]:
            if self.previous_map_key:
                dest = self.previous_map_key
                dx_pos, dy_pos = self.previous_map_pos
                self.current_map_key = dest
                self.player.x = dx_pos
                self.player.y = dy_pos + 1
                self.previous_map_key = None
                return {"moved": True, "portal": True, "dest_map": dest}


        # Check for ground items (pickup)
        ground_items = current_map.get("items", [])
        for gi in ground_items:
            if gi["x"] == new_x and gi["y"] == new_y:
                item_id = gi["item"]
                if item_id == "HM01_CUT":
                    self.player.inventory.obtain_hm("cut")
                elif item_id == "HM02_SURF":
                    self.player.inventory.obtain_hm("surf")
                else:
                    self.player.inventory.add_item(item_id)
                ground_items.remove(gi)
                # Remove tile visually
                row_list = list(current_map["layout"][new_y])
                row_list[new_x] = "d"
                current_map["layout"][new_y] = "".join(row_list)
                return {"moved": True, "tile": tile, "pickup": True, "item_name": gi.get("name", item_id)}
        # Check for encounters
        if tile == 'g':
            enc_rate = current_map.get("encounter_rate", 20)
            if self.rng.randint(1, 100) <= enc_rate:
                return self._trigger_wild_encounter(current_map, new_y)

        # Arena bounds removed - final battle triggers via NPC interaction only

        return {"moved": True, "tile": tile, "surf_mount": surf["mount"], "surf_dismount": surf["dismount"]}

    def _trigger_wild_encounter(self, current_map, player_y):
        """Spawn wild creature based on zone."""
        wild_table = current_map.get("wild_creatures", [])
        if not wild_table:
            return {"moved": True, "tile": "g"}

        # Zone-based encounters
        map_height = current_map["height"]
        if player_y < map_height // 3:
            zone = "top"
        elif player_y < 2 * map_height // 3:
            zone = "middle"
        else:
            zone = "bottom"

        zone_creatures = [e for e in wild_table if e.get("zone", "all") in (zone, "all")]
        if not zone_creatures:
            zone_creatures = wild_table

        entry = self.rng.choice(zone_creatures)
        level = self.rng.randint(entry["min_level"], entry["max_level"])
        wild = make_creature_from_rom(entry["species_id"], level, self.rom)

        active = self.player.active_creature()
        if active is None:
            self.state = "GAME_OVER"
            return {"game_over": True}

        self.battle = BattleEngine(active, wild)
        self.state = "BATTLE"
        return {"encounter": True, "wild_creature": wild}

    def _trigger_final_battle(self):
        """Start the final battle sequence."""
        if not self.opponent or not self.opponent.team:
            return {"moved": True, "tile": "A"}

        self.final_battle_index = 0
        active = self.player.active_creature()
        if active is None:
            self.state = "GAME_OVER"
            return {"game_over": True}

        enemy = self.opponent.team[0]
        enemy.hp = enemy.max_hp  # full heal opponent for fair fight
        self.battle = BattleEngine(active, enemy, is_final=True)
        self.state = "FINAL_BATTLE"
        return {"final_battle": True, "opponent": self.opponent}

    def try_fish(self):
        """Try to fish at current or adjacent tile."""
        if not self.player.has_rod():
            return {"fail": True, "reason": "no_rod"}

        # Check adjacent tiles for fishing spot
        dx, dy = 0, 0
        if self.player.direction == "up": dy = -1
        elif self.player.direction == "down": dy = 1
        elif self.player.direction == "left": dx = -1
        elif self.player.direction == "right": dx = 1

        target_tile = self.get_tile_at(self.player.x + dx, self.player.y + dy)
        if target_tile not in ('w', 'B', 'F'):
            return {"fail": True, "reason": "no_water"}

        # Random catch
        if self.rng.randint(1, 100) <= 60:
            fishing_table = self.get_current_map().get("fishing_creatures", [])
            if fishing_table:
                entry = self.rng.choice(fishing_table)
                level = self.rng.randint(entry["min_level"], entry["max_level"])
                wild = make_creature_from_rom(entry["species_id"], level, self.rom)
                active = self.player.active_creature()
                if active:
                    self.battle = BattleEngine(active, wild)
                    self.state = "BATTLE"
                    return {"encounter": True, "wild_creature": wild, "fishing": True}
        return {"fail": True, "reason": "nothing_bites"}

    def interact(self):
        """Interact with NPC/sign/door in front of player."""
        if self.state != "EXPLORING":
            return None

        dx, dy = 0, 0
        if self.player.direction == "up": dy = -1
        elif self.player.direction == "down": dy = 1
        elif self.player.direction == "left": dx = -1
        elif self.player.direction == "right": dx = 1

        tx = self.player.x + dx
        ty = self.player.y + dy
        current_map = self.get_current_map()

        # NPC check
        for npc in current_map.get("npcs", []):
            if npc["x"] == tx and npc["y"] == ty:
                # Battle NPC (rival) - trigger final battle on interaction
                if npc.get("battle"):
                    result = self._trigger_final_battle()
                    result["dialogue"] = npc.get("dialogue", "Let's battle!")
                    result["name"] = npc.get("name", "Rival")
                    return result
                result = {"npc": True, "dialogue": npc["dialogue"], "name": npc["name"]}
                # Give item if applicable
                npc_id = f"{npc['x']}_{npc['y']}"
                if npc_id not in self.npc_gifts_given:
                    if "gives" in npc:
                        gift = npc["gives"]
                        if gift == "old_rod":
                            self.player.inventory.add_key_item("old_rod")
                            result["received"] = "Old Rod"
                        elif gift == "old_rod_and_surf":
                            self.player.inventory.add_key_item("old_rod")
                            self.player.inventory.obtain_hm("surf")
                            result["received"] = "Old Rod & HM SURF"
                        elif gift == "hm_cut":
                            self.player.inventory.obtain_hm("cut")
                            active = self.player.active_creature()
                            if active:
                                active.teach_hm("cut")
                            result["received"] = "HM CUT"
                        elif gift == "hm_surf":
                            self.player.inventory.obtain_hm("surf")
                            active = self.player.active_creature()
                            if active:
                                active.teach_hm("surf")
                            result["received"] = "HM SURF"
                        self.npc_gifts_given.add(npc_id)
                    if "reveals" in npc:
                        self.opponent.reveal(npc["reveals"])
                        result["reveal"] = npc["reveals"]
                        self.npc_gifts_given.add(npc_id)
                return result

        # Sign check
        for sign in current_map.get("signs", []):
            if sign["x"] == tx and sign["y"] == ty:
                result = {"sign": True, "text": sign["text"]}
                if sign.get("reveal"):
                    result["reveal"] = sign["reveal"]
                return result

        return {"nothing": True}

    def battle_action(self, action, param=0):
        """Execute battle action."""
        if self.state not in ("BATTLE", "FINAL_BATTLE") or self.battle is None:
            return []

        if action == "attack":
            msgs = self.battle.player_attack(param)
        elif action == "flee":
            msgs = self.battle.try_flee()
        elif action == "capture":
            if self.player.inventory.use_item("pokeball"):
                msgs = self.battle.try_capture()
            else:
                msgs = ["No balls left!"]
        elif action == "potion":
            if self.player.inventory.use_item("potion"):
                self.battle.player.heal(20)
                msgs = [f"{self.battle.player.name} healed 20 HP!"]
                # enemy still attacks
                e_move = random.choice(self.battle.enemy.moves)
                msgs += self.battle._do_attack(self.battle.enemy, self.battle.player, e_move)
            else:
                msgs = ["No potions left!"]
        else:
            return []

        if self.battle.finished:
            if self.state == "FINAL_BATTLE":
                return self._handle_final_battle_end(msgs)
            else:
                if self.battle.result == "captured":
                    self.player.add_creature(self.battle.enemy)
                self.state = "EXPLORING"
                self.battle = None
        return msgs

    def _handle_final_battle_end(self, msgs):
        """Handle final battle progression (multi-creature)."""
        if self.battle.result == "win":
            self.final_battle_index += 1
            if self.final_battle_index >= len(self.opponent.team):
                self.state = "VICTORY"
                self.battle = None
                # Defeating the fixed rival unlocks them as a playable character.
                if self.opponent.character_id == "blue":
                    self.unlocked.add("blue")
                msgs.append("You defeated your rival's entire team! VICTORY!")
            else:
                # Next opponent creature
                next_enemy = self.opponent.team[self.final_battle_index]
                next_enemy.hp = next_enemy.max_hp
                active = self.player.active_creature()
                if active is None:
                    self.state = "GAME_OVER"
                    self.battle = None
                    msgs.append("All your creatures fainted! Game Over.")
                else:
                    self.battle = BattleEngine(active, next_enemy, is_final=True)
                    msgs.append(f"Rival sends out {next_enemy.name} Lv{next_enemy.level}!")
        elif self.battle.result == "lose":
            # try next creature in player team
            active = self.player.active_creature()
            if active is None:
                self.state = "GAME_OVER"
                self.battle = None
                msgs.append("All your creatures fainted! Game Over.")
            else:
                self.battle.player = active
                self.battle.finished = False
                self.battle.result = None
                msgs.append(f"Go, {active.name}!")
        return msgs

    def use_potion_outside(self, creature_idx):
        """Use a potion on a creature outside of battle."""
        if not self.player.inventory.use_item("potion"):
            return "No potions left!"
        if 0 <= creature_idx < len(self.player.team):
            self.player.team[creature_idx].heal(20)
            return f"{self.player.team[creature_idx].name} healed!"
        return "Invalid creature."

    # ---------- Timer & IA (Blue) & centro mappa -----------------------------

    def update(self, dt):
        """Chiamato ogni frame da frontend quando in EXPLORING: aggiorna timer e muove IA."""
        if self.state != "EXPLORING" or self.player is None:
            return None
        # Timer 3 minuti
        self.timer -= dt
        if self.timer <= 0:
            self.timer = 0
            # tempo scaduto -> teletrasporto entrambi al centro e battaglia
            return self._trigger_center_battle("time_up")

        # helper: dentro arena?
        def _in_arena(map_key, x, y):
            if map_key != self.CENTER_MAP:
                return False
            b = self.map_data[map_key].get("arena_bounds")
            if not b: return (x, y) == self.CENTER_POS
            return b["x1"] <= x <= b["x2"] and b["y1"] <= y <= b["y2"]

        # IA Blue: si muove verso il centro
        self.ai_tick += 1
        if self.ai_tick >= self.ai_speed:
            self.ai_tick = 0
            self._ai_step_towards_center()
            # controlla se IA ha raggiunto l'arena
            if _in_arena(self.ai_map_key, self.ai_x, self.ai_y):
                return self._trigger_center_battle("ai_reached")
            # controlla se player ha raggiunto l'arena
            if _in_arena(self.current_map_key, self.player.x, self.player.y):
                return self._trigger_center_battle("player_reached")
        else:
            # check player arena anche senza IA step (per reattività)
            if _in_arena(self.current_map_key, self.player.x, self.player.y):
                return self._trigger_center_battle("player_reached")
            # se IA era già in arena all'avvio del frame, triggera comunque
            if _in_arena(self.ai_map_key, self.ai_x, self.ai_y) and self.current_map_key == self.CENTER_MAP:
                # se IA è già lì e player entra nella mappa centrale, triggera quando player è vicino
                if abs(self.player.x - self.ai_x) <= 5 and abs(self.player.y - self.ai_y) <= 5:
                    return self._trigger_center_battle("ai_waiting")
        return None

    def _trigger_center_battle(self, reason):
        """Teletrasporta l'altro al centro e avvia la battaglia finale."""
        # porta entrambi su area_central centro
        self.current_map_key = self.CENTER_MAP
        self.ai_map_key = self.CENTER_MAP
        cx, cy = self.CENTER_POS
        self.player.x, self.player.y = cx, cy + 1  # player appena sotto il centro
        self.ai_x, self.ai_y = cx, cy  # IA sul centro (dove stava Rival)
        # avvia battaglia finale
        return self._trigger_final_battle()

    def _ai_can_traverse(self, map_key, x, y):
        """IA può attraversare più tipi (ha Cut/Surf virtuali)."""
        layout = self.map_data[map_key]["layout"]
        if not (0 <= y < len(layout) and 0 <= x < len(layout[0])):
            return False
        ch = layout[y][x]
        # IA ignora blocchi Cut/Water come se avesse HM
        if ch in ('T', 'M', 'G', 'W', 'N', 'F', 'H', '[', ']', '^', '~', '`', 'E', 'A'):
            # T = albero è bloccante per IA (non taglia) -> evita, ma se necessario passa
            return False
        # walkable include water/cut per IA
        # consideriamo walkable anche g,d,w,B,C,I,.,N etc
        return True

    def _ai_neighbors(self, map_key, x, y):
        """Ritorna vicini (map_key,x,y) raggiungibili da IA in un passo."""
        res = []
        data = self.map_data[map_key]
        layout = data["layout"]
        h, w = len(layout), len(layout[0])
        # 4 direzioni
        for dx, dy in [(0,-1),(0,1),(-1,0),(1,0)]:
            nx, ny = x+dx, y+dy
            # bordo mappa -> edge connection
            if not (0 <= ny < h and 0 <= nx < w):
                edges = data.get("edge_connections", {})
                direction = None
                if ny < 0: direction="north"
                elif ny >= h: direction="south"
                elif nx < 0: direction="west"
                elif nx >= w: direction="east"
                dest_key = edges.get(direction)
                if dest_key and dest_key in self.map_data:
                    dest_layout = self.map_data[dest_key]["layout"]
                    # landing come in _edge_landing: nearest walkable col/row
                    # semplificato: spawn nearest
                    # per IA basta atterrare su walkable
                    if direction=="north":
                        row = len(dest_layout)-1
                        # trova colonna walkable più vicina a x
                        best=None; bestd=1e9
                        for c in range(len(dest_layout[0])):
                            if self._ai_can_traverse(dest_key,c,row):
                                d=abs(c-x)
                                if d<bestd: bestd=d; best=c
                        if best is not None:
                            res.append((dest_key,best,row))
                    elif direction=="south":
                        row=0
                        best=None; bestd=1e9
                        for c in range(len(dest_layout[0])):
                            if self._ai_can_traverse(dest_key,c,row):
                                d=abs(c-x)
                                if d<bestd: bestd=d; best=c
                        if best is not None:
                            res.append((dest_key,best,row))
                    elif direction=="west":
                        col=len(dest_layout[0])-1
                        best=None; bestd=1e9
                        for r in range(len(dest_layout)):
                            if self._ai_can_traverse(dest_key,col,r):
                                d=abs(r-y)
                                if d<bestd: bestd=d; best=r
                        if best is not None:
                            res.append((dest_key,col,best))
                    elif direction=="east":
                        col=0
                        best=None; bestd=1e9
                        for r in range(len(dest_layout)):
                            if self._ai_can_traverse(dest_key,col,r):
                                d=abs(r-y)
                                if d<bestd: bestd=d; best=r
                        if best is not None:
                            res.append((dest_key,col,best))
                continue
            if self._ai_can_traverse(map_key, nx, ny):
                # evita NPC/sign come per player
                blocked=False
                for npc in data.get("npcs", []):
                    if npc["x"]==nx and npc["y"]==ny and npc.get("name")=="Rival":
                        continue
                    if npc["x"]==nx and npc["y"]==ny:
                        blocked=True; break
                if blocked: continue
                # portal -> teletrasporto diretto
                for portal in data.get("portals", []):
                    if portal["x"]==nx and portal["y"]==ny:
                        res.append((portal["dest_map"], portal["dest_x"], portal["dest_y"]))
                        blocked=True; break
                if blocked: continue
                res.append((map_key,nx,ny))
        # portal da posizione attuale (se IA è su portal tile, può entrare anche senza muoversi? gestito sopra)
        return res

    def _ai_step_towards_center(self):
        """Muove IA di un tile verso il centro con BFS."""
        if self.ai_map_key == self.CENTER_MAP and (self.ai_x, self.ai_y) == self.CENTER_POS:
            return
        target = (self.CENTER_MAP, self.CENTER_POS[0], self.CENTER_POS[1])
        start = (self.ai_map_key, self.ai_x, self.ai_y)
        if start == target:
            return
        # BFS
        from collections import deque
        queue=deque([start])
        prev={start: None}
        visited=set([start])
        found=None
        # limita ricerca per performance
        steps=0
        while queue and steps < 2000:
            cur=queue.popleft()
            steps+=1
            if cur==target:
                found=cur; break
            ck,cx,cy = cur
            for nb in self._ai_neighbors(ck,cx,cy):
                if nb not in visited:
                    visited.add(nb)
                    prev[nb]=cur
                    queue.append(nb)
        if target not in prev and found is None:
            # nessun path: muovi random walkable
            neigh=self._ai_neighbors(self.ai_map_key,self.ai_x,self.ai_y)
            if neigh:
                # preferisci quelli più vicini al target (euclideo su mappa center)
                # scegli random tra vicini
                choice=self.rng.choice(neigh)
                self.ai_map_key, self.ai_x, self.ai_y = choice
                # aggiorna direzione
                if choice[1] > self.ai_x: self.ai_direction="right"
                elif choice[1] < self.ai_x: self.ai_direction="left"
                elif choice[2] > self.ai_y: self.ai_direction="down"
                elif choice[2] < self.ai_y: self.ai_direction="up"
            return
        # ricostruisci path
        path=[]
        cur=target
        while cur is not None and cur != start:
            path.append(cur)
            cur=prev.get(cur)
        path.reverse()
        if path:
            nxt=path[0]
            # aggiorna direzione
            _, nx, ny = nxt
            if nx > self.ai_x: self.ai_direction="right"
            elif nx < self.ai_x: self.ai_direction="left"
            elif ny > self.ai_y: self.ai_direction="down"
            elif ny < self.ai_y: self.ai_direction="up"
            self.ai_map_key, self.ai_x, self.ai_y = nxt
