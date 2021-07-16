from enum import IntEnum, auto, IntFlag

from database.world.WorldDatabaseManager import WorldDatabaseManager, config
from utils.Logger import Logger
from utils.constants.ItemCodes import InventorySlots, InventoryStats, InventoryTypes, ItemSubClasses
from utils.constants.MiscCodes import AttackTypes
from utils.constants.SpellCodes import SpellSchools
from utils.constants.UnitCodes import PowerTypes, Classes, CreatureTypes


# Stats that are modified aura effects. Used in StatManager and when accessing stats.
# Use auto indexing to make expanding much easier.
class UnitStats(IntFlag):
    STRENGTH = auto()
    AGILITY = auto()
    STAMINA = auto()
    INTELLECT = auto()
    SPIRIT = auto()
    HEALTH = auto()
    MANA = auto()
    ENERGY = auto()

    RESISTANCE_PHYSICAL = auto()  # Armor
    RESISTANCE_HOLY = auto()
    RESISTANCE_FIRE = auto()
    RESISTANCE_NATURE = auto()
    RESISTANCE_FROST = auto()
    RESISTANCE_SHADOW = auto()

    MAIN_HAND_DAMAGE_MIN = auto()
    MAIN_HAND_DAMAGE_MAX = auto()
    MAIN_HAND_DELAY = auto()

    OFF_HAND_DAMAGE_MIN = auto()
    OFF_HAND_DAMAGE_MAX = auto()
    OFF_HAND_DELAY = auto()

    RANGED_DAMAGE_MIN = auto()
    RANGED_DAMAGE_MAX = auto()
    RANGED_DELAY = auto()

    PARRY = auto()
    DODGE = auto()
    BLOCK = auto()

    CRITICAL = auto()
    SPELL_CRITICAL = auto()
    SPELL_CASTING_SPEED_NON_STACKING = auto()
    SCHOOL_CRITICAL = auto()
    SCHOOL_POWER_COST = auto()

    DAMAGE_DONE = auto()
    DAMAGE_DONE_SCHOOL = auto()
    DAMAGE_DONE_WEAPON = auto()
    DAMAGE_DONE_CREATURE_TYPE = auto()
    DAMAGE_TAKEN = auto()
    DAMAGE_TAKEN_SCHOOL = auto()

    HEALTH_REGENERATION_PER_5 = auto()
    POWER_REGENERATION_PER_5 = auto()

    ATTACK_SPEED = auto()
    THREAT = auto()
    STEALTH = auto()
    STEALTH_DETECTION = auto()
    INVISIBILITY = auto()
    INVISIBILITY_DETECTION = auto()
    SPEED_RUNNING = auto()
    SPEED_SWIMMING = auto()
    SPEED_MOUNTED = auto()

    SKILL = auto()

    ATTRIBUTE_START = STRENGTH
    RESISTANCE_START = RESISTANCE_PHYSICAL

    ALL_ATTRIBUTES = STRENGTH | AGILITY | STAMINA | INTELLECT | SPIRIT
    # Exclude armor
    ALL_RESISTANCES = RESISTANCE_HOLY | RESISTANCE_FIRE | RESISTANCE_NATURE | RESISTANCE_FROST | RESISTANCE_SHADOW


class StatManager(object):

    # Player base stats and misc. stats scaling off items (weapon damage etc.)
    base_stats: dict[UnitStats, int]

    # Stat gain from items
    item_stats: dict[UnitStats, int]

    # Managed by AuraManager. [Aura index, (Stat, bonus, misc value)]
    # Misc value can contain power/weapon/creature type etc. depending on the stat
    aura_stats_flat: dict[int, (UnitStats, int, int)]
    aura_stats_percentual: dict[int, (UnitStats, float, int, int)]

    weapon_reach: float

    def __init__(self, player_mgr):
        self.player_mgr = player_mgr

        self.weapon_reach = 0

        self.base_stats = {}
        self.item_stats = {}

        self.aura_stats_flat = {}
        self.aura_stats_percentual = {}

    def init_stats(self):
        base_stats = WorldDatabaseManager.player_get_class_level_stats(self.player_mgr.player.class_,
                                                                       self.player_mgr.level)
        base_attrs = WorldDatabaseManager.player_get_level_stats(self.player_mgr.player.class_,
                                                                 self.player_mgr.level,
                                                                 self.player_mgr.player.race)

        if not base_stats or not base_attrs:
            Logger.error(f'Unsupported level ({self.player_mgr.level}) from {self.player_mgr.player.name}.')
            return

        self.base_stats[UnitStats.HEALTH] = base_stats.basehp
        self.base_stats[UnitStats.MANA] = base_stats.basemana
        self.base_stats[UnitStats.STRENGTH] = base_attrs.str
        self.base_stats[UnitStats.AGILITY] = base_attrs.agi
        self.base_stats[UnitStats.STAMINA] = base_attrs.sta
        self.base_stats[UnitStats.INTELLECT] = base_attrs.inte
        self.base_stats[UnitStats.SPIRIT] = base_attrs.spi
        self.base_stats[UnitStats.SPEED_RUNNING] = config.Unit.Defaults.run_speed

        self.player_mgr.base_hp = base_stats.basehp
        self.player_mgr.base_mana = base_stats.basemana

        self.send_attributes()

        self.update_base_health_regen()
        self.update_base_mana_regen()

    def get_base_stat(self, stat_type: UnitStats) -> int:
        return self.base_stats.get(stat_type, 0)

    def get_item_stat(self, stat_type: UnitStats) -> int:
        return self.item_stats.get(stat_type, 0)

    def get_stat_gain_from_aura_bonuses(self, stat_type: UnitStats, misc_value=-1) -> int:
        # Note: bonus can be negative due to harmful effects.
        base_stats = self.get_base_stat(stat_type)
        item_stats = self.get_item_stat(stat_type)
        bonus_stats = self.get_aura_stat_bonus(stat_type, misc_value=misc_value)

        total = int((base_stats + item_stats + bonus_stats) * self.get_aura_stat_bonus(stat_type, percentual=True, misc_value=misc_value))

        return total - base_stats - item_stats

    def get_total_stat(self, stat_type: UnitStats, misc_value=-1, accept_negative=False) -> int:
        base_stats = self.get_base_stat(stat_type)
        bonus_stats = self.item_stats.get(stat_type, 0) + self.get_aura_stat_bonus(stat_type, misc_value=misc_value)

        total = int((base_stats + bonus_stats) * self.get_aura_stat_bonus(stat_type, percentual=True, misc_value=misc_value))

        if accept_negative:
            return total

        return max(0, total)  # Stats are always positive

    def apply_bonuses(self):
        self.calculate_item_stats()

        # Always update base attack since unarmed damage should update.
        self.update_base_weapon_attributes(attack_type=AttackTypes.BASE_ATTACK)

        if self.player_mgr.inventory.get_offhand():
            self.update_base_weapon_attributes(attack_type=AttackTypes.OFFHAND_ATTACK)
        if self.player_mgr.inventory.get_ranged():  # TODO Are ranged formulas different?
            self.update_base_weapon_attributes(attack_type=AttackTypes.RANGED_ATTACK)

        self.player_mgr.change_speed(self.get_total_stat(UnitStats.SPEED_RUNNING))

        hp_diff = self.update_max_health()
        mana_diff = self.update_max_mana()

        self.update_base_mana_regen()
        self.update_base_health_regen()

        self.send_attributes()
        self.send_melee_attributes()
        self.send_damage_bonuses()
        self.send_resistances()

        self.player_mgr.skill_manager.build_update()
        self.player_mgr.set_dirty()

        return hp_diff, mana_diff

    def apply_bonuses_for_value(self, value: int, stat_type: UnitStats, misc_value=-1, misc_value_is_mask=False):
        flat = self.get_aura_stat_bonus(stat_type, misc_value=misc_value, misc_value_is_mask=misc_value_is_mask)
        percentual = self.get_aura_stat_bonus(stat_type, percentual=True, misc_value=misc_value, misc_value_is_mask=misc_value_is_mask)
        return int((value + flat) * percentual)

    def apply_aura_stat_bonus(self, index: int, stat_type: UnitStats, amount: int, misc_value=-1, percentual=False):
        if percentual:
            self.aura_stats_percentual[index] = (stat_type, amount, misc_value)
        else:
            self.aura_stats_flat[index] = (stat_type, amount, misc_value)

        self.apply_bonuses()

    def remove_aura_stat_bonus(self, index: int, percentual=False):
        if percentual:
            self.aura_stats_percentual.pop(index)
        else:
            self.aura_stats_flat.pop(index)

        self.apply_bonuses()

    def get_aura_stat_bonus(self, stat_type: UnitStats, percentual=False, misc_value=-1, misc_value_is_mask=False):
        if percentual:
            target_bonuses = self.aura_stats_percentual
            bonus = 1
        else:
            target_bonuses = self.aura_stats_flat
            bonus = 0

        for stat_bonus in target_bonuses.values():
            if not stat_bonus[0] & stat_type:
                # Stat bonus type or misc value don't match
                continue

            if misc_value != -1 or stat_bonus[2] != -1:
                if misc_value_is_mask and not misc_value & stat_bonus[2] or \
                        (not misc_value_is_mask and misc_value != stat_bonus[2]):
                    continue

            if not percentual:
                bonus += stat_bonus[1]
            else:
                bonus *= stat_bonus[1] / 100 + 1

        return bonus

    # TODO move to formulas instead?
    @staticmethod
    def get_health_bonus_from_stamina(stamina):
        # The first 20 points of Stamina grant only 1 health point per unit.
        base_sta = stamina if stamina < 20 else 20
        more_sta = stamina - base_sta
        return base_sta + (more_sta * 10.0)

    @staticmethod
    def get_mana_bonus_from_intellect(intellect):
        # The first 20 points of Intellect grant only 1 mana point per unit.
        base_int = intellect if intellect < 20 else 20
        more_int = intellect - base_int
        return base_int + (more_int * 15.0)

    def calculate_item_stats(self):
        self.item_stats = {UnitStats.MAIN_HAND_DELAY: config.Unit.Defaults.base_attack_time,
                           UnitStats.OFF_HAND_DELAY: config.Unit.Defaults.offhand_attack_time}  # Clear item stats
        self.weapon_reach = 0

        for slot, item in list(self.player_mgr.inventory.get_backpack().sorted_slots.items()):
            # Check only equipped items
            if item.current_slot <= InventorySlots.SLOT_TABARD:
                for stat in item.stats:
                    if stat.stat_type == 0:
                        continue
                    stat_type = INVENTORY_STAT_TO_UNIT_STAT[stat.stat_type]
                    current = self.item_stats.get(stat_type, 0)
                    self.item_stats[stat_type] = current + stat.value

                # Add resistances/block
                separate_stats = {UnitStats.RESISTANCE_PHYSICAL: item.item_template.armor,
                                  UnitStats.RESISTANCE_HOLY: item.item_template.holy_res,
                                  UnitStats.RESISTANCE_FIRE: item.item_template.fire_res,
                                  UnitStats.RESISTANCE_NATURE: item.item_template.nature_res,
                                  UnitStats.RESISTANCE_FROST: item.item_template.frost_res,
                                  UnitStats.RESISTANCE_SHADOW: item.item_template.shadow_res,
                                  UnitStats.BLOCK: item.item_template.block}
                for stat, value in separate_stats.items():
                    self.item_stats[stat] = self.item_stats.get(stat, 0) + value

                weapon_min_damage = int(item.item_template.dmg_min1)
                weapon_max_damage = int(item.item_template.dmg_max1)
                weapon_delay = item.item_template.delay

                if item.current_slot == InventorySlots.SLOT_MAINHAND:
                    self.item_stats[UnitStats.MAIN_HAND_DAMAGE_MIN] = weapon_min_damage
                    self.item_stats[UnitStats.MAIN_HAND_DAMAGE_MAX] = weapon_max_damage
                    self.item_stats[UnitStats.MAIN_HAND_DELAY] = weapon_delay
                elif item.current_slot == InventorySlots.SLOT_OFFHAND:
                    dual_wield_penalty = 0.5
                    self.item_stats[UnitStats.OFF_HAND_DAMAGE_MIN] = int(weapon_min_damage * dual_wield_penalty)
                    self.item_stats[UnitStats.OFF_HAND_DAMAGE_MAX] = int(weapon_max_damage * dual_wield_penalty)
                    self.item_stats[UnitStats.OFF_HAND_DELAY] = weapon_delay
                elif item.current_slot == InventorySlots.SLOT_RANGED:
                    self.item_stats[UnitStats.RANGED_DAMAGE_MIN] = weapon_min_damage
                    self.item_stats[UnitStats.RANGED_DAMAGE_MAX] = weapon_max_damage
                    self.item_stats[UnitStats.RANGED_DELAY] = weapon_delay

                current_reach = self.weapon_reach
                weapon_reach = StatManager.get_reach_for_weapon(item.item_template)
                if current_reach == -1 or current_reach > weapon_reach:
                    self.weapon_reach = weapon_reach

    # TODO move to formulas?
    @staticmethod
    def get_reach_for_weapon(item_template):
        # This is a TOTAL guess, I have no idea about real weapon reach values.
        # The weapon reach unit field was removed in patch 0.10.
        if item_template.inventory_type == InventoryTypes.TWOHANDEDWEAPON:
            return 1.5
        elif item_template.subclass == ItemSubClasses.ITEM_SUBCLASS_DAGGER:
            return 0.5
        elif item_template.subclass != ItemSubClasses.ITEM_SUBCLASS_FIST_WEAPON:
            return 1.0

    def update_max_health(self):
        total_stamina = self.get_total_stat(UnitStats.STAMINA)
        total_health = self.get_total_stat(UnitStats.HEALTH)

        current_hp = self.player_mgr.max_health
        new_hp = int(self.get_health_bonus_from_stamina(total_stamina) + total_health)
        self.player_mgr.set_max_health(new_hp)

        hp_diff = new_hp - current_hp

        return hp_diff if hp_diff > 0 else 0

    def update_max_mana(self):
        if self.player_mgr.power_type != PowerTypes.TYPE_MANA:
            return 0

        total_intellect = self.get_total_stat(UnitStats.INTELLECT)
        total_mana = self.get_total_stat(UnitStats.MANA)

        current_mana = self.player_mgr.max_power_1
        new_mana = int(self.get_mana_bonus_from_intellect(total_intellect) + total_mana)
        self.player_mgr.set_max_mana(new_mana)

        mana_diff = new_mana - current_mana

        return mana_diff if mana_diff > 0 else 0

    def update_base_health_regen(self):
        player_class = self.player_mgr.player.class_
        class_spirit_scaling = {
            Classes.CLASS_WARRIOR: 1.26,
            Classes.CLASS_PALADIN: 0.25,
            Classes.CLASS_HUNTER: 0.43,
            Classes.CLASS_ROGUE: 0.84,
            Classes.CLASS_PRIEST: 0.15,
            Classes.CLASS_SHAMAN: 0.28,
            Classes.CLASS_MAGE: 0.11,
            Classes.CLASS_WARLOCK: 0.12,
            Classes.CLASS_DRUID: 0.11
        }
        class_base_regen = {
            Classes.CLASS_WARRIOR: -22.6,
            Classes.CLASS_PALADIN: 0.0,
            Classes.CLASS_HUNTER: -5.5,
            Classes.CLASS_ROGUE: -13,
            Classes.CLASS_PRIEST: 1.4,
            Classes.CLASS_SHAMAN: -3.6,
            Classes.CLASS_MAGE: 1.0,
            Classes.CLASS_WARLOCK: 1.5,
            Classes.CLASS_DRUID: 1.0
        }

        spirit = self.get_total_stat(UnitStats.SPIRIT)
        self.base_stats[UnitStats.HEALTH_REGENERATION_PER_5] = int(class_base_regen[player_class] + spirit * class_spirit_scaling[player_class])


    def update_base_mana_regen(self):
        player_class = self.player_mgr.player.class_
        class_spirit_scaling = {
            Classes.CLASS_WARRIOR: 0.0,
            Classes.CLASS_PALADIN: 0.20,
            Classes.CLASS_HUNTER: 0.0,
            Classes.CLASS_ROGUE: 0.0,
            Classes.CLASS_PRIEST: 0.25,
            Classes.CLASS_SHAMAN: 0.20,
            Classes.CLASS_MAGE: 0.25,
            Classes.CLASS_WARLOCK: 0.2,
            Classes.CLASS_DRUID: 0.2
        }
        class_base_regen = {
            Classes.CLASS_WARRIOR: -22.6,
            Classes.CLASS_PALADIN: 15.0,
            Classes.CLASS_HUNTER: 12.5,
            Classes.CLASS_ROGUE: -13.0,
            Classes.CLASS_PRIEST: 12.5,
            Classes.CLASS_SHAMAN: 17.0,
            Classes.CLASS_MAGE: 12.5,
            Classes.CLASS_WARLOCK: 15.0,
            Classes.CLASS_DRUID: 15.0
        }

        spirit = self.get_total_stat(UnitStats.SPIRIT)
        regen = class_base_regen[player_class] + spirit * class_spirit_scaling[player_class]
        self.base_stats[UnitStats.POWER_REGENERATION_PER_5] = int(regen / 2)

    # Auto attack/shoot base damage
    def get_base_attack_base_min_max_damage(self, attack_type: AttackTypes):
        if attack_type == AttackTypes.BASE_ATTACK:
            weapon_min_damage = self.get_total_stat(UnitStats.MAIN_HAND_DAMAGE_MIN)
            weapon_max_damage = self.get_total_stat(UnitStats.MAIN_HAND_DAMAGE_MAX)
        elif attack_type == AttackTypes.OFFHAND_ATTACK:
            weapon_min_damage = self.get_total_stat(UnitStats.OFF_HAND_DAMAGE_MIN)
            weapon_max_damage = self.get_total_stat(UnitStats.OFF_HAND_DAMAGE_MAX)
        else:
            weapon_min_damage = self.get_total_stat(UnitStats.RANGED_DAMAGE_MIN)
            weapon_max_damage = self.get_total_stat(UnitStats.RANGED_DAMAGE_MAX)

        return weapon_min_damage, weapon_max_damage

    def apply_bonuses_for_damage(self, damage, attack_school: SpellSchools, target_creature_type: CreatureTypes, weapon_type: ItemSubClasses = -1):
        if weapon_type != -1:
            weapon_type = 1 << weapon_type
        else:
            weapon_type = 0

        flat_bonuses = self.get_aura_stat_bonus(UnitStats.DAMAGE_DONE_SCHOOL, percentual=False, misc_value=attack_school) + \
            self.get_aura_stat_bonus(UnitStats.DAMAGE_DONE_WEAPON, percentual=False, misc_value=weapon_type, misc_value_is_mask=True) + \
            self.get_aura_stat_bonus(UnitStats.DAMAGE_DONE_CREATURE_TYPE, percentual=False, misc_value=target_creature_type)

        percentual_bonuses = self.get_aura_stat_bonus(UnitStats.DAMAGE_DONE_SCHOOL, percentual=True, misc_value=attack_school) * \
            self.get_aura_stat_bonus(UnitStats.DAMAGE_DONE_WEAPON, percentual=True, misc_value=weapon_type, misc_value_is_mask=True) * \
            self.get_aura_stat_bonus(UnitStats.DAMAGE_DONE_CREATURE_TYPE, percentual=True, misc_value=target_creature_type)

        return (damage + flat_bonuses) * percentual_bonuses

    def update_base_weapon_attributes(self, attack_type=0):
        # TODO: Using Vanilla formula, AP was not present in Alpha

        dual_wield_penalty = 1 if attack_type != AttackTypes.OFFHAND_ATTACK else 0.5

        attack_power = 0
        strength = self.get_total_stat(UnitStats.STRENGTH)
        agility = self.get_total_stat(UnitStats.AGILITY)
        level = self.player_mgr.level
        class_ = self.player_mgr.player.class_


        # TODO Formula tables instead
        if class_ == Classes.CLASS_WARRIOR or \
                class_ == Classes.CLASS_PALADIN:
            attack_power = (strength * 2) + (level * 3) - 20
        elif class_ == Classes.CLASS_DRUID:
            attack_power = (strength * 2) - 20
        elif class_ == Classes.CLASS_HUNTER:
            attack_power = strength + agility + (level * 2) - 20
        elif class_ == Classes.CLASS_MAGE or \
                class_ == Classes.CLASS_PRIEST or \
                class_ == Classes.CLASS_WARLOCK:
            attack_power = strength - 10
        elif class_ == Classes.CLASS_ROGUE:
            attack_power = strength + ((agility * 2) - 20) + (level * 2) - 20
        elif class_ == Classes.CLASS_SHAMAN:
            attack_power = strength - 10 + ((agility * 2) - 20) + (level * 2)

        final_min_damage = attack_power / 14 * dual_wield_penalty
        final_max_damage = attack_power / 14 * dual_wield_penalty

        if attack_type == AttackTypes.BASE_ATTACK:
            self.base_stats[UnitStats.MAIN_HAND_DAMAGE_MIN] = final_min_damage
            self.base_stats[UnitStats.MAIN_HAND_DAMAGE_MAX] = final_max_damage
        elif attack_type == AttackTypes.OFFHAND_ATTACK:
            self.base_stats[UnitStats.OFF_HAND_DAMAGE_MIN] = final_min_damage
            self.base_stats[UnitStats.OFF_HAND_DAMAGE_MAX] = final_max_damage
        else:
            self.base_stats[UnitStats.RANGED_DAMAGE_MIN] = final_min_damage
            self.base_stats[UnitStats.RANGED_DAMAGE_MAX] = final_max_damage

    def update_defense_bonuses(self):
        pass

    def send_melee_attributes(self):
        # For stat sheet
        self.player_mgr.set_melee_damage(self.get_total_stat(UnitStats.MAIN_HAND_DAMAGE_MIN),
                                         self.get_total_stat(UnitStats.MAIN_HAND_DAMAGE_MAX))

        self.player_mgr.set_melee_attack_time(self.get_total_stat(UnitStats.MAIN_HAND_DELAY))
        self.player_mgr.set_offhand_attack_time(self.get_total_stat(UnitStats.OFF_HAND_DELAY))
        self.player_mgr.set_weapon_reach(self.weapon_reach)

    def send_resistances(self):
        self.player_mgr.set_armor(self.get_total_stat(UnitStats.RESISTANCE_PHYSICAL, accept_negative=True))
        self.player_mgr.set_holy_res(self.get_total_stat(UnitStats.RESISTANCE_HOLY, accept_negative=True))
        self.player_mgr.set_fire_res(self.get_total_stat(UnitStats.RESISTANCE_FIRE, accept_negative=True))
        self.player_mgr.set_nature_res(self.get_total_stat(UnitStats.RESISTANCE_NATURE, accept_negative=True))
        self.player_mgr.set_frost_res(self.get_total_stat(UnitStats.RESISTANCE_FROST, accept_negative=True))
        self.player_mgr.set_shadow_res(self.get_total_stat(UnitStats.RESISTANCE_SHADOW, accept_negative=True))

        # TODO Distinguish between positive and negative buffs (client seems to be able to display both at the same time)
        self.player_mgr.set_bonus_armor(self.get_stat_gain_from_aura_bonuses(UnitStats.RESISTANCE_PHYSICAL))
        self.player_mgr.set_bonus_holy_res(self.get_stat_gain_from_aura_bonuses(UnitStats.RESISTANCE_HOLY))
        self.player_mgr.set_bonus_fire_res(self.get_stat_gain_from_aura_bonuses(UnitStats.RESISTANCE_FIRE))
        self.player_mgr.set_bonus_nature_res(self.get_stat_gain_from_aura_bonuses(UnitStats.RESISTANCE_NATURE))
        self.player_mgr.set_bonus_frost_res(self.get_stat_gain_from_aura_bonuses(UnitStats.RESISTANCE_FROST))
        self.player_mgr.set_bonus_shadow_res(self.get_stat_gain_from_aura_bonuses(UnitStats.RESISTANCE_SHADOW))

    def send_attributes(self):
        self.player_mgr.set_base_str(self.get_base_stat(UnitStats.STRENGTH))
        self.player_mgr.set_base_agi(self.get_base_stat(UnitStats.AGILITY))
        self.player_mgr.set_base_sta(self.get_base_stat(UnitStats.STAMINA))
        self.player_mgr.set_base_int(self.get_base_stat(UnitStats.INTELLECT))
        self.player_mgr.set_base_spi(self.get_base_stat(UnitStats.SPIRIT))

        # TODO Should the stat display be allowed to show negative values?
        self.player_mgr.set_str(self.get_total_stat(UnitStats.STRENGTH, accept_negative=True))
        self.player_mgr.set_agi(self.get_total_stat(UnitStats.AGILITY, accept_negative=True))
        self.player_mgr.set_sta(self.get_total_stat(UnitStats.STAMINA, accept_negative=True))
        self.player_mgr.set_int(self.get_total_stat(UnitStats.INTELLECT, accept_negative=True))
        self.player_mgr.set_spi(self.get_total_stat(UnitStats.SPIRIT, accept_negative=True))

    def send_damage_bonuses(self):
        main_hand = self.player_mgr.inventory.get_main_hand()
        subclass_mask = 0
        if main_hand:
            subclass_mask = 1 << main_hand.item_template.subclass

        for school in SpellSchools:
            flat_bonuses = self.get_aura_stat_bonus(UnitStats.DAMAGE_DONE_SCHOOL, misc_value=school) + \
                self.get_aura_stat_bonus(UnitStats.DAMAGE_DONE_WEAPON, misc_value=subclass_mask, misc_value_is_mask=True)

            percentual_bonuses = self.get_aura_stat_bonus(UnitStats.DAMAGE_DONE_SCHOOL, misc_value=school, percentual=True) * \
                self.get_aura_stat_bonus(UnitStats.DAMAGE_DONE_WEAPON, misc_value=subclass_mask, percentual=True, misc_value_is_mask=True)

            self.player_mgr.set_bonus_damage_done_for_school(int(flat_bonuses * percentual_bonuses), school)


INVENTORY_STAT_TO_UNIT_STAT = {
    InventoryStats.MANA: UnitStats.MANA,
    InventoryStats.HEALTH: UnitStats.HEALTH,
    InventoryStats.AGILITY: UnitStats.AGILITY,
    InventoryStats.STRENGTH: UnitStats.STRENGTH,
    InventoryStats.INTELLECT: UnitStats.INTELLECT,
    InventoryStats.SPIRIT: UnitStats.SPIRIT,
    InventoryStats.STAMINA: UnitStats.STAMINA
}