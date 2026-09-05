"""
The Final Battle - Core game engine.
Full game loop: character select, spawn, explore, collect, discover, final battle.
All creature/move data read from ROM at runtime.
"""

import json
import os
import random
from rom_reader import RomReader, find_rom, _get_type_multiplier_int, TYPE_NAMES

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
    def __init__(self, name, power, accuracy=100, element="normal", move_id=0, is_hm=False,
                 high_crit=False, category="physical"):
        self.name = name
        self.power = power
        self.accuracy = accuracy
        self.element = element
        self.move_id = move_id
        self.is_hm = is_hm
        self.high_crit = high_crit
        self.category = category  # "physical" or "special"

    def __repr__(self):
        return f"Move({self.name}, pwr={self.power}, {self.element})"


# Physical types in Gen 3 (everything before TYPE_MYSTERY=9 is physical)
_PHYSICAL_TYPES = {"normal", "fighting", "flying", "poison", "ground", "rock", "bug", "ghost", "steel"}


class Creature:
    def __init__(self, species_id, name, element, base_hp, base_atk, base_def,
                 base_spd, level=5, moves=None, element2=None,
                 base_spatk=None, base_spdef=None):
        self.species_id = species_id
        self.name = name
        self.element = element
        self.element2 = element2 or element
        self.base_hp = base_hp
        self.base_atk = base_atk
        self.base_def = base_def
        self.base_spd = base_spd
        self.base_spatk = base_spatk if base_spatk is not None else base_atk
        self.base_spdef = base_spdef if base_spdef is not None else base_def
        self.level = level
        self.moves = moves or []
        self.max_hp = self._calc_hp()
        self.hp = self.max_hp
        self.atk = self._calc_stat(base_atk)
        self.defense = self._calc_stat(base_def)
        self.spd = self._calc_stat(base_spd)
        self.spatk = self._calc_stat(self.base_spatk)
        self.spdef = self._calc_stat(self.base_spdef)
        self.can_surf = False
        self.can_cut = False
        self.can_rock_smash = False
        self.can_strength = False
        # Stat stages (6 = default, 0..12 range)
        self.stat_stages = {"atk": 6, "def": 6, "spatk": 6, "spdef": 6, "spd": 6, "acc": 6, "eva": 6}

    def _calc_hp(self):
        return int((self.base_hp * 2 * self.level) / 100) + self.level + 10

    def _calc_stat(self, base):
        return int((base * 2 * self.level) / 100) + 5

    def get_effective_stat(self, stat_name):
        """Get stat value with stage modifier applied."""
        attr = "defense" if stat_name == "def" else stat_name
        base_val = getattr(self, attr, 0)
        stage = self.stat_stages.get(stat_name, 6)
        ratios = [(10,40),(10,35),(10,30),(10,25),(10,20),(10,15),
                  (10,10),(15,10),(20,10),(25,10),(30,10),(35,10),(40,10)]
        num, den = ratios[max(0, min(12, stage))]
        return max(1, int(base_val * num / den))

    def is_fainted(self):
        return self.hp <= 0

    def take_damage(self, dmg):
        self.hp = max(0, self.hp - dmg)

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    def teach_hm(self, hm_name, rom=None):
        """Teach HM move. Returns True if successful, False if species can't learn it."""
        if rom and not rom.can_learn_hm(self.species_id, hm_name):
            return False
        if hm_name == "cut":
            self.can_cut = True
            if not any(m.name == "CUT" for m in self.moves):
                self.moves.append(Move("CUT", 50, 95, "normal", is_hm=True, category="physical"))
        elif hm_name == "surf":
            self.can_surf = True
            if not any(m.name == "SURF" for m in self.moves):
                self.moves.append(Move("SURF", 90, 100, "water", is_hm=True, category="special"))
        elif hm_name == "rock_smash":
            self.can_rock_smash = True
            if not any(m.name == "ROCK_SMASH" for m in self.moves):
                self.moves.append(Move("ROCK_SMASH", 40, 100, "fighting", is_hm=True, category="physical"))
        elif hm_name == "strength":
            self.can_strength = True
            if not any(m.name == "STRENGTH" for m in self.moves):
                self.moves.append(Move("STRENGTH", 80, 100, "normal", is_hm=True, category="physical"))
        return True

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
                element=move_data["element"], move_id=mid,
                category="physical" if move_data["element"] in _PHYSICAL_TYPES else "special",
            ))

    if not move_objs:
        for lv, mid in learnable[:4]:
            move_data = rom_reader.read_battle_move(mid)
            if move_data:
                move_objs.append(Move(
                    name=move_data["name"],
                    power=max(move_data["power"], 30),
                    accuracy=move_data["accuracy"] if move_data["accuracy"] > 0 else 100,
                    element=move_data["element"], move_id=mid,
                    category="physical" if move_data["element"] in _PHYSICAL_TYPES else "special",
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

# Stat stage ratios from ROM: stage_index -> (numerator, denominator)
_STAT_STAGE_RATIOS = [
    (10,40),(10,35),(10,30),(10,25),(10,20),(10,15),
    (10,10),(15,10),(20,10),(25,10),(30,10),(35,10),(40,10)
]

# Accuracy stage ratios from ROM
_ACC_STAGE_RATIOS = [
    (33,100),(36,100),(43,100),(50,100),(60,100),(75,100),
    (1,1),(133,100),(166,100),(2,1),(233,100),(133,50),(3,1)
]

# Critical hit rates by stage: 1/N
_CRIT_CHANCES = [16, 8, 4, 3, 2]

# High-crit move effects from ROM
_HIGH_CRIT_EFFECTS = {43, 209, 210, 44}  # EFFECT_HIGH_CRITICAL + others


class BattleEngine:
    def __init__(self, player_creature, enemy_creature, is_final=False, rom_data=None):
        self.player = player_creature
        self.enemy = enemy_creature
        self.log = []
        self.turn = 0
        self.finished = False
        self.result = None
        self.is_final = is_final
        self.rom_data = rom_data
        self.anim_events = []

    def _calc_crit_stage(self, attacker, move):
        """Calculate critical hit stage from move flags."""
        stage = 0
        if move.high_crit:
            stage += 1
        if move.element in ("poison",) and move.name in ("POISON_TAIL",):
            stage += 1
        return min(stage, len(_CRIT_CHANCES) - 1)

    def _roll_crit(self, attacker, move):
        """Roll for critical hit. Returns True if crit."""
        stage = self._calc_crit_stage(attacker, move)
        chance = _CRIT_CHANCES[stage]
        return random.randint(1, chance) == 1

    def _calc_accuracy(self, attacker, defender, move):
        """Gen 3 accuracy formula. Returns True if move hits."""
        if move.accuracy == 0:
            return True  # always-hit moves (Swift, etc.)
        # Combined accuracy-evasion stage
        acc_stage = attacker.stat_stages.get("acc", 6)
        eva_stage = defender.stat_stages.get("eva", 6)
        buff = acc_stage + 6 - eva_stage
        buff = max(0, min(12, buff))
        # Apply stage ratio to move accuracy
        num, den = _ACC_STAGE_RATIOS[buff]
        calc = num * move.accuracy // den
        # Roll for hit
        return random.randint(1, 100) <= calc

    def calc_damage(self, attacker, defender, move, is_crit=False):
        """Replicates the GBA FireRed damage formula exactly (integer math).

        Mirrors pokefirered src/pokemon.c CalculateBaseDamage + Cmd_damagecalc +
        Cmd_typecalc + ApplyRandomDmgMultiplier, in the same order with the same
        integer truncation at every step.
        """
        if move.power == 0:
            return 0, "", False

        is_physical = move.category == "physical"

        # --- CalculateBaseDamage -----------------------------------------
        if is_physical:
            atk_stat = attacker.get_effective_stat("atk")
            def_stat = defender.get_effective_stat("def")
            # Crit ignores attacker's -stages and defender's +stages
            if is_crit:
                if attacker.stat_stages["atk"] < 6:
                    atk_stat = attacker.atk
                if defender.stat_stages["def"] > 6:
                    def_stat = defender.defense
        else:
            atk_stat = attacker.get_effective_stat("spatk")
            def_stat = defender.get_effective_stat("spdef")
            if is_crit:
                if attacker.stat_stages["spatk"] < 6:
                    atk_stat = attacker.spatk
                if defender.stat_stages["spdef"] > 6:
                    def_stat = defender.spdef

        # damage = atk * power ; damage *= (2*level/5 + 2)   (integer div)
        level = attacker.level
        damage = atk_stat * move.power
        damage *= (2 * level // 5 + 2)
        damage //= max(1, def_stat)
        damage //= 50

        # Burn halves physical damage (ROM applies it inside base damage, pre-STAB)
        burn = bool(is_physical and hasattr(attacker, 'status') and attacker.status == "burn")
        if burn:
            damage //= 2

        base = damage + 2

        # --- Cmd_damagecalc: crit multiplier (2x in Gen 3) ----------------
        if is_crit:
            base *= 2

        # --- Cmd_typecalc: STAB then type (integer x/10 each) -------------
        if move.element in (attacker.element, attacker.element2):
            base = base * 15 // 10
        type_mult, type_msg = _get_type_multiplier_int(
            move.element, defender.element, defender.element2, self.rom_data)
        if type_mult != 0:
            base = base * type_mult // 10
            if base == 0:
                base = 1
        else:
            # Immune: ModulateDmgByType(0) leaves damage at 0 (no min-1 bump)
            base = 0

        # --- ApplyRandomDmgMultiplier: 85-100% ---------------------------
        if base != 0:
            rand_percent = 100 - (random.randint(0, 15))
            base = base * rand_percent // 100
            if base == 0:
                base = 1

        return base, type_msg, is_crit

    def player_attack(self, move_index):
        if self.finished:
            return []
        self.anim_events = []
        self.turn += 1
        messages = []
        move_idx = min(move_index, len(self.player.moves) - 1)
        p_move = self.player.moves[move_idx]

        # Speed-based turn order
        player_first = self.player.spd >= self.enemy.spd

        if player_first:
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
            messages.append(f"{self.enemy.name} fainted!")
        elif self.player.is_fainted():
            self.finished = True
            self.result = "lose"
            messages.append(f"{self.player.name} fainted!")

        self.log.extend(messages)
        return messages

    def try_flee(self):
        if self.finished:
            return []
        self.anim_events = []
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
        self.anim_events = []
        if self.is_final:
            return ["Can't capture your rival's creature!"]
        # Gen 3 catch formula simplified
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
        msgs = []
        side_atk = "player" if attacker is self.player else "enemy"
        side_def = "player" if defender is self.player else "enemy"
        # Accuracy check
        if not self._calc_accuracy(attacker, defender, move):
            msgs.append(f"{attacker.name} used {move.name}... but missed!")
            self.anim_events.append({
                "atk": side_atk, "def": side_def,
                "move": move.name, "move_type": move.element,
                "category": move.category, "power": move.power,
                "dmg": 0, "crit": False, "hit": False, "miss": True,
            })
            return msgs

        # Critical hit roll
        is_crit = self._roll_crit(attacker, move)

        # Calculate damage with full Gen 3 formula
        dmg, type_msg, _ = self.calc_damage(attacker, defender, move, is_crit)
        defender.take_damage(dmg)

        self.anim_events.append({
            "atk": side_atk, "def": side_def,
            "move": move.name, "move_type": move.element,
            "category": move.category, "power": move.power,
            "dmg": dmg, "crit": is_crit, "hit": True, "miss": False,
        })

        # Build message
        msg = f"{attacker.name} used {move.name}!"
        if is_crit:
            msg += " A critical hit!"
        if type_msg == "super":
            msg += " It's super effective!"
        elif type_msg == "weak":
            msg += " It's not very effective..."
        elif type_msg == "immune":
            msg += f" It doesn't affect {defender.name}..."
        msg += f" ({dmg} dmg)"
        msgs.append(msg)
        return msgs


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
        # Blue starts with only the starter and builds the team during the run.
        starter = make_creature_from_rom(starter_species, 8, rom)
        starter.teach_hm("cut", rom)
        starter.teach_hm("surf", rom)
        self.team.append(starter)
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

    # Default center (overridden per-rival in start_game)
    CENTER_MAP = "area_central"
    CENTER_POS = (10, 5)
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
        self.removed_rocks = set()     # IDs of smashed breakable rocks
        self.pushed_boulders = set()   # IDs of pushed boulders
        self.final_battle_index = 0  # which opponent creature we're fighting
        self.current_map_key = "forest_south"  # default, set in start_game
        self.previous_map_key = None
        self.previous_map_pos = (0, 0)
        self.unlocked = set()  # character ids unlockable by defeating their rival (e.g. "blue")
        # Center map (set per-rival in start_game)
        self.center_map = self.CENTER_MAP
        self.center_pos = self.CENTER_POS
        # Timer & IA (Blue)
        self.timer = self.TIMER_SECONDS
        self.ai_x = 0
        self.ai_y = 0
        self.ai_map_key = "forest_south"
        self.ai_direction = "down"
        self.ai_tick = 0  # frames since last AI step
        self.ai_speed = 18  # frames per tile (più lento del player)
        self.ai_log = []  # per indizi dinamici: cosa ha fatto Blue
        self.ai_level_timer = 0  # per level up periodico
        self.ai_route = "north"
        self.ai_has_cut = False
        self.ai_has_surf = False
        self.ai_waypoints = []
        self.ai_waypoint_index = 0

    def load_data(self, rom_path=None):
        if rom_path is None:
            rom_path = find_rom()
        if rom_path is None:
            raise FileNotFoundError("No .gba ROM found. Use --rom <path>.")
        self.rom = RomReader(rom_path)
        self.map_data = load_json("maps.json")
        self.characters = load_json("characters.json")

    def start_game(self, character_id, starter_species_id, seed=None, map_key=None):
        """Start with chosen character + starter. Random spawn or chosen map."""
        self.seed = seed if seed is not None else random.randint(0, 99999)
        self.rng = random.Random(self.seed)

        starter = make_creature_from_rom(starter_species_id, 5, self.rom)
        char_data = self.characters[character_id]
        self.player = PlayerState(character_id, starter, char_data.get("starting_items"))

        if map_key and map_key == "rock_desert":
            spawn_maps_desert = ["rock_desert", "rock_desert_shelter"]
            self.current_map_key = self.rng.choice(spawn_maps_desert)
        elif map_key and map_key == "darkwood":
            spawn_maps = ["forest_south", "forest_north"]
            self.current_map_key = self.rng.choice(spawn_maps)
        elif map_key and map_key in self.map_data:
            self.current_map_key = map_key
        else:
            spawn_maps = ["forest_south", "forest_north"]
            self.current_map_key = self.rng.choice(spawn_maps)
        current = self.map_data[self.current_map_key]

        # Opponent: Brock on rock_desert/shelter, Blue elsewhere
        is_desert = self.current_map_key in ("rock_desert", "rock_desert_shelter")
        if is_desert and "brock" in self.characters:
            opp_char = "brock"
        else:
            opp_char = "blue" if "blue" in self.characters else next(
                c for c in self.characters if c != character_id
            )
        opp_starters = self.characters[opp_char]["starter_options"]
        opp_starter = self.rng.choice(opp_starters)["species"]
        self.opponent = OpponentState(opp_char, opp_starter, self.rom)

        # Set center map per rival
        if is_desert:
            self.center_map = "rock_desert_arena"
            self.center_pos = (10, 7)
        else:
            self.center_map = "area_central"
            self.center_pos = (10, 5)

        # Timer e IA
        self.timer = self.TIMER_SECONDS
        self.ai_has_cut = True
        self.ai_has_surf = True

        if is_desert:
            self.ai_route = "desert"
            current = self.map_data[self.current_map_key]
            spawn = current.get("spawn", current.get("spawn_desert", [22, 17]))
            self.player.x, self.player.y = spawn[0], spawn[1]
            self.ai_spawn_side = "east"
            # Brock spawns in the opposite area from player
            if self.current_map_key == "rock_desert":
                # Player in desert -> Brock in shelter, trains on g tiles -> arena -> center
                self.ai_map_key = "rock_desert_shelter"
                self.ai_x, self.ai_y = 5, 6
                self.ai_waypoints = [
                    ("rock_desert_shelter", 4, 13),
                    ("rock_desert_shelter", 14, 13),
                    ("rock_desert_shelter", 4, 12),
                    ("rock_desert_shelter", 14, 12),
                    ("rock_desert_arena", 8, 4),
                    ("rock_desert_arena", 11, 4),
                    ("rock_desert_arena", 8, 11),
                    ("rock_desert_arena", 11, 11),
                    ("rock_desert_arena", 10, 7),
                ]
                self.ai_log = [f"Brock è partito da {self.map_data['rock_desert_shelter']['name']}"]
            else:
                # Player in shelter -> Brock in desert, trains on z tiles -> arena -> center
                self.ai_map_key = "rock_desert"
                self.ai_x, self.ai_y = 22, 16
                self.ai_waypoints = [
                    ("rock_desert", 19, 15),
                    ("rock_desert", 22, 15),
                    ("rock_desert", 19, 17),
                    ("rock_desert", 22, 17),
                    ("rock_desert_arena", 8, 4),
                    ("rock_desert_arena", 11, 4),
                    ("rock_desert_arena", 8, 11),
                    ("rock_desert_arena", 11, 11),
                    ("rock_desert_arena", 10, 7),
                ]
                self.ai_log = [f"Brock è partito da {self.map_data['rock_desert']['name']}"]
        elif self.current_map_key == "forest_south":
            # Player on forest_south -> Blue on forest_north -> training in grass -> area_central
            self.ai_map_key = "forest_north"
            sp_ai = self.map_data["forest_north"]["spawn"]
            self.ai_x, self.ai_y = sp_ai[0], sp_ai[1]
            self.ai_route = "south"
            self.ai_waypoints = [
                ("forest_north", 14, 10),
                ("forest_north", 6, 4),
                ("forest_north", 22, 4),
                ("forest_north", 14, 18),
                ("forest_north", 14, 20),
                ("area_central", 10, 1),
                ("area_central", 10, 5),
            ]
        elif self.current_map_key == "forest_north":
            # Player on forest_north -> Blue on forest_south -> training in grass -> river -> area_central
            self.ai_map_key = "forest_south"
            sp_ai = self.map_data["forest_south"]["spawn"]
            self.ai_x, self.ai_y = sp_ai[0], sp_ai[1]
            self.ai_route = "north"
            self.ai_waypoints = [
                ("forest_south", 14, 10),
                ("forest_south", 10, 8),
                ("forest_south", 20, 8),
                ("river_area", 14, 0),
                ("river_area", 5, 5),
                ("area_central", 10, 12),
                ("area_central", 10, 5),
            ]
        else:
            # Fallback: Blue on forest_north -> area_central
            self.ai_map_key = "forest_north"
            sp_ai = self.map_data["forest_north"]["spawn"]
            self.ai_x, self.ai_y = sp_ai[0], sp_ai[1]
            self.ai_route = "north"
            self.ai_waypoints = [
                ("forest_north", 14, 10),
                ("forest_north", 6, 4),
                ("area_central", 10, 1),
                ("area_central", 10, 5),
            ]

        if not is_desert:
            sp = current["spawn"]
            self.player.x, self.player.y = sp[0], sp[1]
        self.ai_waypoint_index = 0
        self.ai_direction = "down"
        self.ai_tick = 0
        # Rival loops first N waypoints (grass training) until team is full
        rival_name = self.characters.get(self.opponent.character_id, {}).get("name", "Rival")
        self.ai_training_end = 4 if is_desert else 3  # desert: 4 local encounters, forest: 2
        self.ai_log = [f"{rival_name} è partito da {self.map_data[self.ai_map_key]['name']}"]
        self.ai_level_timer = 0
        # log iniziale team
        if self.opponent.team:
            self.ai_log.append(f"{rival_name} ha {len(self.opponent.team)} creature, la più forte è Lv{max(c.level for c in self.opponent.team)}")

        self.state = "EXPLORING"















    def get_current_map(self):
        return self.map_data.get(self.current_map_key, {})

    def get_tile_at(self, x, y):
        """Get tile character at position, accounting for cut tiles and broken rocks."""
        if (x, y) in self.cut_tiles_removed:
            return 'd'
        rock_id = f"{self.current_map_key}_rock_{x}_{y}"
        if rock_id in self.removed_rocks:
            # All current breakable rocks stand on desert sand.  Returning
            # sand keeps collision and the post-animation render in sync.
            return 'z'
        layout = self.map_data[self.current_map_key]["layout"]
        if 0 <= y < len(layout) and 0 <= x < len(layout[y]):
            return layout[y][x]
        return 'T'

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

        # Breakable rock requires Spaccaroccia
        elif tile == 'R':
            return {"blocked": True, "reason": "need_rock_smash"}

        # Boulder requires Forza to push (use interact)
        elif tile == 'b':
            return {"blocked": True, "reason": "need_strength"}

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
        encounter_tiles = current_map.get("encounter_tiles", ["g"])
        if tile in encounter_tiles:
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

        self.battle = BattleEngine(active, wild, rom_data=getattr(self, 'rom', None) and self.rom.data)
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
        self.battle = BattleEngine(active, enemy, is_final=True, rom_data=getattr(self, 'rom', None) and self.rom.data)
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
                    self.battle = BattleEngine(active, wild, rom_data=getattr(self, 'rom', None) and self.rom.data)
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
                # Se NPC è marcato dynamic, dai indizio su Blue (ogni partita diversa)
                base_dial = npc["dialogue"]
                if (npc.get("dynamic") or npc.get("is_rumor")
                    or npc.get("name") != "Fisher"):
                    clue = self.get_ai_clue()
                    base_dial = f"{base_dial} [Indizio: {clue}]"
                result = {"npc": True, "dialogue": base_dial, "name": npc["name"]}
                # Give item if applicable
                npc_id = f"{npc['x']}_{npc['y']}"
                if npc_id not in self.npc_gifts_given:
                    gift_key = "gives" if "gives" in npc else "gift"
                    if gift_key in npc:
                        gift = npc[gift_key]
                        if gift == "old_rod":
                            self.player.inventory.add_key_item("old_rod")
                            result["received"] = "Old Rod"
                        elif gift == "old_rod_and_surf":
                            self.player.inventory.add_key_item("old_rod")
                            self.player.inventory.obtain_hm("surf")
                            result["received"] = "Old Rod & HM SURF"
                            result["teach_hm"] = "surf"
                        elif gift == "potion_x3":
                            self.player.inventory.add_item("potion", 3)
                            result["received"] = "3 Potions"
                        elif gift == "hm_cut":
                            self.player.inventory.obtain_hm("cut")
                            result["received"] = "HM CUT"
                            result["teach_hm"] = "cut"
                        elif gift == "hm_surf":
                            self.player.inventory.obtain_hm("surf")
                            result["received"] = "HM SURF"
                            result["teach_hm"] = "surf"
                        elif gift == "dratini":
                            dratini = make_creature_from_rom(147, 15, self.rom)
                            if self.player.add_creature(dratini):
                                result["received"] = "Dratini"
                            else:
                                result["received"] = "Dratini (team full!)"
                        elif gift == "ponyta":
                            ponyta = make_creature_from_rom(77, 15, self.rom)
                            if self.player.add_creature(ponyta):
                                result["received"] = "Ponyta"
                            else:
                                result["received"] = "Ponyta (team full!)"
                        elif gift == "rock_smash":
                            self.player.inventory.obtain_hm("rock_smash")
                            result["received"] = "HM Spaccaroccia"
                            result["teach_hm"] = "rock_smash"
                        elif gift == "strength":
                            self.player.inventory.obtain_hm("strength")
                            result["received"] = "HM Forza"
                            result["teach_hm"] = "strength"
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
                if sign.get("is_rumor"):
                    result["text"] = f"{result['text']} [Indizio: {self.get_ai_clue()}]"
                return result

        # Breakable rock check (Spaccaroccia)
        current_map_key = self.current_map_key
        for rock in current_map.get("breakable_rocks", []):
            if rock["x"] == tx and rock["y"] == ty:
                rock_id = f"{current_map_key}_rock_{rock['x']}_{rock['y']}"
                if rock_id in self.removed_rocks:
                    return {"nothing": True}
                if self.player.inventory.has_hm("rock_smash"):
                    # A field move may be supplied by any conscious member of
                    # the party; requiring the currently selected creature
                    # made a legitimately taught HM appear unusable.
                    if any(getattr(creature, "can_rock_smash", False)
                           for creature in self.player.team):
                        # The front end commits the removal only after the
                        # breaking animation has played.  Removing it here
                        # makes the first rendered animation frame show the
                        # replacement terrain instead of the rock.
                        return {"rock_smash": True, "rock_x": rock["x"], "rock_y": rock["y"], "rock_id": rock_id}
                    else:
                        return {"npc": True, "dialogue": "It's a big rock. If only I had Spaccaroccia...", "name": "Rock"}
                else:
                    return {"npc": True, "dialogue": "It's a big rock. If only I had Spaccaroccia...", "name": "Rock"}

        # Boulder check (Forza / Strength)
        for boulder in current_map.get("boulders", []):
            if boulder["x"] == tx and boulder["y"] == ty:
                boulder_id = f"{current_map_key}_boulder_{boulder['x']}_{boulder['y']}"
                if boulder_id in self.pushed_boulders:
                    return {"nothing": True}
                if self.player.inventory.has_hm("strength"):
                    active = self.player.active_creature()
                    if active and any(m.name == "STRENGTH" for m in active.moves):
                        # Push boulder in facing direction
                        push = boulder.get("pushes_to", {})
                        px, py = push.get("x", tx + dx), push.get("y", ty + dy)
                        dest_layout = current_map["layout"]
                        if 0 <= py < len(dest_layout) and 0 <= px < len(dest_layout[0]):
                            dest_ch = dest_layout[py][px]
                            if dest_ch in ('z', 'd', 'A'):
                                self.pushed_boulders.add(boulder_id)
                                layout = list(current_map["layout"])
                                old_row = list(layout[boulder["y"]])
                                old_row[boulder["x"]] = 'z'
                                layout[boulder["y"]] = ''.join(old_row)
                                current_map["layout"] = layout
                                return {"npc": True, "dialogue": "The boulder was pushed aside!", "name": "Boulder"}
                        return {"npc": True, "dialogue": "I can't push it here.", "name": "Boulder"}
                    else:
                        return {"npc": True, "dialogue": "It's a huge boulder. If only I had Forza...", "name": "Boulder"}
                else:
                    return {"npc": True, "dialogue": "It's a huge boulder. If only I had Forza...", "name": "Boulder"}

        return {"nothing": True}

    def battle_action(self, action, param=0):
        """Execute battle action."""
        if self.state not in ("BATTLE", "FINAL_BATTLE") or self.battle is None:
            return []
        self.battle.anim_events = []

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
            elif self.battle.result == "captured":
                self.player.add_creature(self.battle.enemy)
                self.state = "EXPLORING"
                self.battle = None
            elif self.battle.result == "win":
                self.state = "EXPLORING"
                self.battle = None
            elif self.battle.result == "lose":
                # Wild battle: try next creature in player team
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
            else:
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
                if self.opponent.character_id in ("blue", "brock"):
                    self.unlocked.add(self.opponent.character_id)
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
                    self.battle = BattleEngine(active, next_enemy, is_final=True, rom_data=getattr(self, 'rom', None) and self.rom.data)
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
            if map_key != self.center_map:
                return False
            b = self.map_data[map_key].get("arena_bounds")
            if not b: return (x, y) == self.center_pos
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
            if _in_arena(self.ai_map_key, self.ai_x, self.ai_y) and self.current_map_key == self.center_map:
                # se IA è già lì e player entra nella mappa centrale, triggera quando player è vicino
                if abs(self.player.x - self.ai_x) <= 5 and abs(self.player.y - self.ai_y) <= 5:
                    return self._trigger_center_battle("ai_waiting")
        return None

    def _trigger_center_battle(self, reason):
        """Teletrasporta l'altro al centro e avvia la battaglia finale."""
        # porta entrambi al centro della mappa del rival corrente
        self.current_map_key = self.center_map
        self.ai_map_key = self.center_map
        cx, cy = self.center_pos
        self.player.x, self.player.y = cx, cy + 1  # player appena sotto il centro
        self.ai_x, self.ai_y = cx, cy  # IA sul centro (dove sta Rival)
        # avvia battaglia finale
        return self._trigger_final_battle()

    def _ai_can_traverse(self, map_key, x, y):
        """IA può attraversare più tipi (ha Cut/Surf virtuali)."""
        layout = self.map_data[map_key]["layout"]
        if not (0 <= y < len(layout) and 0 <= x < len(layout[0])):
            return False
        ch = layout[y][x]
        if map_key == self.center_map:
            bounds = self.map_data[map_key].get("arena_bounds", {})
            if (bounds.get("x1", 0) <= x <= bounds.get("x2", -1)
                    and bounds.get("y1", 0) <= y <= bounds.get("y2", -1)):
                return True
        if any(portal["x"] == x and portal["y"] == y
               for portal in self.map_data[map_key].get("portals", [])):
            return True
        if ch == 'C':
            return self.ai_has_cut
        if ch in ('w', 'B'):
            return self.ai_has_surf
        # IA ignora blocchi Cut/Water come se avesse HM
        if ch in ('T', 'M', 'G', 'W', 'N', 'F', 'H', '[', ']', '^', '~', '`', 'E', 'R', 'b', 'Q', 'P'):
            return False
        # Arena is walkable for IA (gym leader moves inside)
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
                    if (self.ai_route == "north" and not self.ai_has_cut
                            and dest_key == self.center_map):
                        continue
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
                        if (self.ai_route == "north" and not self.ai_has_cut
                                and portal["dest_map"] == self.center_map):
                            blocked = True
                            break
                        res.append((portal["dest_map"], portal["dest_x"], portal["dest_y"]))
                        blocked=True; break
                if blocked: continue
                # dynamic_exit -> torna alla mappa precedente
                dyn = data.get("dynamic_exit")
                if dyn and nx == dyn["x"] and ny == dyn["y"]:
                    prev_map = self.previous_map_key or map_key
                    if prev_map in self.map_data:
                        prev_spawn = self.map_data[prev_map].get("spawn", [10, 10])
                        res.append((prev_map, prev_spawn[0], prev_spawn[1]))
                    blocked = True
                if blocked: continue
                res.append((map_key,nx,ny))
        # portal da posizione attuale (se IA è su portal tile, può entrare anche senza muoversi? gestito sopra)
        return res

    def _ai_handle_post_move(self):
        """Dopo aver mosso il rivale, simula gioco: encounters, catture, log per indizi dinamici."""
        rival_name = self.characters.get(self.opponent.character_id, {}).get("name", "Rival")
        # ogni tanto level up (più lento: ~60s)
        self.ai_level_timer += 1
        if self.ai_level_timer >= 3600:
            self.ai_level_timer = 0
            for c in self.opponent.team:
                c.level = min(20, c.level + 1)
                c.max_hp = c._calc_hp(); c.hp = c.max_hp
            self.ai_log.append(f"{rival_name} si è allenato, ora Lv{max(c.level for c in self.opponent.team)}")
            if len(self.ai_log) > 12: self.ai_log.pop(0)
        # check tall grass / desert encounter - priorità: riempire la squadra
        try:
            layout = self.map_data[self.ai_map_key]["layout"]
            ch = layout[self.ai_y][self.ai_x] if 0 <= self.ai_y < len(layout) and 0 <= self.ai_x < len(layout[0]) else '.'
            encounter_tiles = self.map_data[self.ai_map_key].get("encounter_tiles", ["g"])
            if ch in encounter_tiles:
                wild_table = self.map_data[self.ai_map_key].get("wild_creatures", [])
                if wild_table and len(self.opponent.team) < 6:
                    if self.rng.random() < 0.05:
                        entry = self.rng.choice(wild_table)
                        lvl = self.rng.randint(entry["min_level"], entry["max_level"])
                        wild = make_creature_from_rom(entry["species_id"], lvl, self.rom)
                        self.opponent.team.append(wild)
                        self.ai_log.append(f"{rival_name} ha catturato {wild.name} Lv{lvl} in {self.map_data[self.ai_map_key]['name']}")
                        if len(self.ai_log) > 12: self.ai_log.pop(0)
                        self.opponent.known_team_count = True
                elif self.opponent.team and len(self.opponent.team) < 6 and self.rng.random() < 0.03:
                    #level up graduale quando squadra non è piena
                    c = max(self.opponent.team, key=lambda creature: creature.level)
                    c.level = min(20, c.level + 1)
                    c.max_hp = c._calc_hp()
                    c.hp = c.max_hp
                    self.ai_log.append(f"Il {c.name} di {rival_name} è salito a Lv{c.level}")
                    if len(self.ai_log) > 12: self.ai_log.pop(0)
        except Exception:
            pass

    def get_ai_clue(self):
        """Ritorna un indizio dinamico basato su cosa ha fatto il rivale (ogni partita diversa)."""
        rival_name = self.characters.get(self.opponent.character_id, {}).get("name", "Rival")
        if not self.ai_log:
            return f"{rival_name} si sta muovendo verso il centro..."
        # preferisci ultimi 3 log, pick random per variabilità
        recent = self.ai_log[-3:]
        return self.rng.choice(recent)

    def _ai_step_towards_center(self):
        """Muove IA verso il centro con BFS + 15% random walk + training loop."""
        # 15% random walk per rendere ogni partita diversa e cacciare
        if self.rng.random() < 0.15:
            neigh = self._ai_neighbors(self.ai_map_key, self.ai_x, self.ai_y)
            if neigh:
                choice = self.rng.choice(neigh)
                if choice[1] > self.ai_x: self.ai_direction="right"
                elif choice[1] < self.ai_x: self.ai_direction="left"
                elif choice[2] > self.ai_y: self.ai_direction="down"
                elif choice[2] < self.ai_y: self.ai_direction="up"
                self.ai_map_key, self.ai_x, self.ai_y = choice
                self._ai_handle_post_move()
            return

        # Se squadra non è piena, resta nelle prime N waypoints (training loop)
        team_full = len(self.opponent.team) >= 6
        training_end = getattr(self, 'ai_training_end', 0)
        if not team_full and training_end > 0 and self.ai_waypoint_index >= training_end:
            self.ai_waypoint_index = 0

        if not self.ai_waypoints:
            return
        current = (self.ai_map_key, self.ai_x, self.ai_y)
        target = self.ai_waypoints[self.ai_waypoint_index]
        if current == target:
            if self.ai_waypoint_index < len(self.ai_waypoints) - 1:
                self.ai_waypoint_index += 1
                target = self.ai_waypoints[self.ai_waypoint_index]
            else:
                # Reached final destination (center) - stay there, just do post-move
                self._ai_handle_post_move()
                return
            if current == target:
                return

        from collections import deque
        queue = deque([current])
        previous = {current: None}
        while queue and target not in previous:
            position = queue.popleft()
            for neighbor in self._ai_neighbors(*position):
                if neighbor not in previous:
                    previous[neighbor] = position
                    queue.append(neighbor)

        if target not in previous:
            rival_name = self.characters.get(self.opponent.character_id, {}).get("name", "Rival")
            self.ai_log.append(f"{rival_name} non trova il percorso verso {target[0]}")
            return

        path = []
        next_position = target
        while next_position != current:
            path.append(next_position)
            next_position = previous.get(next_position)
            if next_position is None:
                rival_name = self.characters.get(self.opponent.character_id, {}).get("name", "Rival")
                self.ai_log.append(f"{rival_name} non trova il percorso verso {target[0]}")
                return
        next_position = path[-1]
        _, next_x, next_y = next_position
        if next_position[0] == self.ai_map_key:
            if next_x > self.ai_x:
                self.ai_direction = "right"
            elif next_x < self.ai_x:
                self.ai_direction = "left"
            elif next_y > self.ai_y:
                self.ai_direction = "down"
            elif next_y < self.ai_y:
                self.ai_direction = "up"
            if self.map_data[self.ai_map_key]["layout"][next_y][next_x] == "C":
                self.cut_tiles_removed.add((next_x, next_y))
        self.ai_map_key, self.ai_x, self.ai_y = next_position
        self._ai_handle_post_move()
