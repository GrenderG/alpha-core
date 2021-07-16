import time
from struct import pack
from typing import Optional

from database.dbc.DbcDatabaseManager import DbcDatabaseManager
from database.dbc.DbcModels import Spell, SpellRange, SpellDuration, SpellCastTimes
from game.world.managers.abstractions.Vector import Vector
from game.world.managers.maps.MapManager import MapManager
from game.world.managers.objects.ObjectManager import ObjectManager
from game.world.managers.objects.item.ItemManager import ItemManager
from game.world.managers.objects.player.StatManager import UnitStats
from game.world.managers.objects.spell.SpellEffect import SpellEffect
from network.packet.PacketWriter import PacketWriter
from utils.constants.MiscCodes import AttackTypes, ObjectTypes
from utils.constants.OpCodes import OpCode
from utils.constants.SpellCodes import SpellState, SpellCastFlags, SpellTargetMask, SpellAttributes, SpellAttributesEx, \
    AuraTypes, SpellSchools, SpellEffects, SpellInterruptFlags


class CastingSpell(object):
    spell_entry: Spell
    cast_state: SpellState
    cast_flags: SpellCastFlags  # TODO Write proc flag when needed
    spell_caster = None
    source_item = None
    initial_target = None
    targeted_unit_on_cast_start = None

    object_target_results = {}  # Assigned on cast - contains guids and results on successful hits/misses/blocks etc.
    spell_target_mask: SpellTargetMask
    range_entry: SpellRange
    duration_entry: SpellDuration
    cast_time_entry: SpellCastTimes
    effects: list

    cast_start_timestamp: float
    cast_end_timestamp: float
    spell_impact_timestamps: dict[int, float]
    caster_effective_level: int

    spell_attack_type: int

    def __init__(self, spell, caster_obj, initial_target, target_mask, source_item=None):
        self.spell_entry = spell
        self.spell_caster = caster_obj
        self.source_item = source_item
        self.initial_target = initial_target
        self.spell_target_mask = target_mask
        self.duration_entry = DbcDatabaseManager.spell_duration_get_by_id(spell.DurationIndex)
        self.range_entry = DbcDatabaseManager.spell_range_get_by_id(spell.RangeIndex)  # TODO RangeMin is never used
        self.cast_time_entry = DbcDatabaseManager.spell_cast_time_get_by_id(spell.CastingTimeIndex)
        self.cast_end_timestamp = self.get_base_cast_time()/1000 + time.time()
        self.caster_effective_level = self.calculate_effective_level(self.spell_caster.level)

        self.spell_attack_type = -1  # Assigned on cast TODO Next ranged spells
        self.cast_state = SpellState.SPELL_STATE_PREPARING
        self.spell_impact_timestamps = {}

        if ObjectTypes.TYPE_PLAYER in caster_obj.object_type:
            self.targeted_unit_on_cast_start = MapManager.get_surrounding_unit_by_guid(self.spell_caster, self.spell_caster.current_selection, include_players=True)

        self.load_effects()

        self.cast_flags = SpellCastFlags.CAST_FLAG_NONE  # TODO Ammo/proc flag

    def initial_target_is_object(self):
        return isinstance(self.initial_target, ObjectManager)

    def initial_target_is_unit_or_player(self):
        if not self.initial_target_is_object():
            return False

        target_type = self.initial_target.get_type()
        return target_type == ObjectTypes.TYPE_UNIT or target_type == ObjectTypes.TYPE_PLAYER

    def initial_target_is_player(self):
        if not self.initial_target_is_object():
            return False

        return self.initial_target.get_type() == ObjectTypes.TYPE_PLAYER

    def initial_target_is_item(self):
        if not self.initial_target_is_object():
            return False

        return self.initial_target.get_type() == ObjectTypes.TYPE_ITEM

    def initial_target_is_gameobject(self):
        if not self.initial_target_is_object():
            return False

        return self.initial_target.get_type() == ObjectTypes.TYPE_GAMEOBJECT

    def initial_target_is_terrain(self):
        return isinstance(self.initial_target, Vector)

    def get_initial_target_info(self):  # ([values], len)
        is_terrain = self.initial_target_is_terrain()
        return ([self.initial_target.x, self.initial_target.y, self.initial_target.z] if is_terrain
                else [self.initial_target.guid]), ('3f' if is_terrain else 'Q')

    def resolve_target_info_for_effects(self):
        for effect in self.effects:
            self.resolve_target_info_for_effect(effect.effect_index)

    # noinspection PyUnresolvedReferences
    def resolve_target_info_for_effect(self, index):
        if index < 0 or index > len(self.effects) - 1:
            return
        effect = self.effects[index]
        if not effect:
            return

        effect.targets.resolve_targets()
        effect_info = effect.targets.get_effect_target_miss_results()
        self.object_target_results = {**self.object_target_results, **effect_info}

    def is_instant_cast(self):
        return self.cast_time_entry.Base <= 0  # One entry has negative (-1000000) base cast time and should be instant.

    def is_ranged(self):
        return self.spell_entry.Attributes & SpellAttributes.SPELL_ATTR_RANGED == SpellAttributes.SPELL_ATTR_RANGED

    def is_passive(self):
        return self.spell_entry.Attributes & SpellAttributes.SPELL_ATTR_PASSIVE == SpellAttributes.SPELL_ATTR_PASSIVE

    def is_channeled(self):
        return self.spell_entry.AttributesEx & SpellAttributesEx.SPELL_ATTR_EX_CHANNELED

    def generates_threat(self):
        return not (self.spell_entry.AttributesEx & SpellAttributesEx.SPELL_ATTR_EX_NO_THREAT)

    def is_refreshment_spell(self):
        if len(self.effects) == 0:
            return False
        spell_effect = self.effects[0]  # Food/drink effect should be first
        has_sitting_attribute = self.spell_entry.Attributes & SpellAttributes.SPELL_ATTR_CASTABLE_WHILE_SITTING
        is_regen_buff = spell_effect.aura_type == AuraTypes.SPELL_AURA_PERIODIC_HEAL or \
            spell_effect.aura_type == AuraTypes.SPELL_AURA_PERIODIC_ENERGIZE

        return has_sitting_attribute and is_regen_buff

    def is_paladin_aura(self):  # Paladin aura casts are the only holy area auras TODO table in constants instead?
        return self.spell_entry.School == SpellSchools.SPELL_SCHOOL_HOLY and \
               self.spell_entry.Effect_1 == SpellEffects.SPELL_EFFECT_APPLY_AREA_AURA and \
               self.spell_entry.EffectRadiusIndex_1 != 0  # One unrelated (unfinished? Has area aura effect but isn't functional) spell matches other criteria, but has no radius entry

    def trigger_cooldown_on_aura_remove(self):
        return self.spell_entry.Attributes & SpellAttributes.SPELL_ATTR_DISABLED_WHILE_ACTIVE == SpellAttributes.SPELL_ATTR_DISABLED_WHILE_ACTIVE

    def casts_on_swing(self):
        return self.spell_entry.Attributes & SpellAttributes.SPELL_ATTR_ON_NEXT_SWING_1 == SpellAttributes.SPELL_ATTR_ON_NEXT_SWING_1

    def requires_combo_points(self):
        cp_att = SpellAttributesEx.SPELL_ATTR_EX_REQ_TARGET_COMBO_POINTS | SpellAttributesEx.SPELL_ATTR_EX_REQ_COMBO_POINTS
        return self.spell_caster.get_type() == ObjectTypes.TYPE_PLAYER and \
            self.spell_entry.AttributesEx & cp_att != 0

    def requires_hostile_target(self):
        for effect in self.effects:
            if not effect.targets.can_target_friendly():
                return True
        return False

    def calculate_effective_level(self, level):
        if level > self.spell_entry.MaxLevel > 0:
            level = self.spell_entry.MaxLevel
        elif level < self.spell_entry.BaseLevel:
            level = self.spell_entry.BaseLevel
        return max(level - self.spell_entry.SpellLevel, 0)

    def get_base_cast_time(self):
        if self.is_instant_cast():
            return 0
        skill = self.spell_caster.skill_manager.get_skill_value_for_spell_id(self.spell_entry.ID)
        if not skill:
            return self.cast_time_entry.Minimum

        return int(max(self.cast_time_entry.Minimum, self.cast_time_entry.Base + self.cast_time_entry.PerLevel * skill))

    def get_resource_cost(self):
        mana_cost = self.spell_entry.ManaCost
        power_cost_mod = 0

        if self.spell_caster.get_type() == ObjectTypes.TYPE_PLAYER and self.spell_entry.ManaCostPct != 0:
            mana_cost = self.spell_caster.base_mana * self.spell_entry.ManaCostPct / 100

        if self.spell_caster.get_type() == ObjectTypes.TYPE_PLAYER:
            mana_cost = self.spell_caster.stat_manager.apply_bonuses_for_value(mana_cost, UnitStats.SCHOOL_POWER_COST,
                                                                               misc_value=self.spell_entry.School)
        # ManaCostPerLevel is not used by anything relevant, ignore for now (only 271/4513/7290) TODO

        return mana_cost + power_cost_mod

    def load_effects(self):
        self.effects = []
        if self.spell_entry.Effect_1 != 0:
            self.effects.append(SpellEffect(self, len(self.effects)))
        if self.spell_entry.Effect_2 != 0:
            self.effects.append(SpellEffect(self, len(self.effects)))
        if self.spell_entry.Effect_3 != 0:
            self.effects.append(SpellEffect(self, len(self.effects)))  # Use effects length for index - some spells (by mistake?) have empty effect slots before an actual effect

    def get_reagents(self):
        return (self.spell_entry.Reagent_1, self.spell_entry.ReagentCount_1), (self.spell_entry.Reagent_2, self.spell_entry.ReagentCount_2), \
               (self.spell_entry.Reagent_3, self.spell_entry.ReagentCount_3), (self.spell_entry.Reagent_4, self.spell_entry.ReagentCount_4), \
               (self.spell_entry.Reagent_5, self.spell_entry.ReagentCount_5), (self.spell_entry.Reagent_6, self.spell_entry.ReagentCount_6), \
               (self.spell_entry.Reagent_7, self.spell_entry.ReagentCount_7), (self.spell_entry.Reagent_8, self.spell_entry.ReagentCount_8)

    def get_item_spell_stats(self) -> Optional[ItemManager.SpellStat]:
        if not self.source_item:
            return None
        for spell_info in self.source_item.spell_stats:
            if spell_info.spell_id == self.spell_entry.ID:
                return spell_info
        return None

    def get_required_tools(self):
        return [self.spell_entry.Totem_1, self.spell_entry.Totem_2]

    def get_conjured_items(self):
        conjured_items = []
        for effect in self.effects:
            item_count = abs(effect.get_effect_points(self.caster_effective_level))
            conjured_items.append([effect.item_type, item_count])
        return tuple(conjured_items)

    def handle_partial_interrupt(self):
        if not self.spell_entry.InterruptFlags & SpellInterruptFlags.SPELL_INTERRUPT_FLAG_PARTIAL:
            return

        # TODO Did pushback resistance exist?
        curr_time = time.time()
        remaining_cast_before_pushback = self.cast_end_timestamp - curr_time

        if self.is_channeled() and self.cast_state == SpellState.SPELL_STATE_ACTIVE:
            channel_length = self.duration_entry.Duration/1000  # /1000 for seconds.
            final_opcode = OpCode.MSG_CHANNEL_UPDATE
            pushback_length_sec = min(remaining_cast_before_pushback, channel_length * 0.25)
            for effect in self.effects:
                if remaining_cast_before_pushback <= pushback_length_sec:
                    # Applied aura duration is not timestamp based so it's stored in milliseconds.
                    # To avoid rounding issues, set to zero instead of subtracting if pushback leads to channel stop.
                    effect.applied_aura_duration = 0
                else:
                    effect.applied_aura_duration -= pushback_length_sec * 1000  # aura duration is stored as millis.
                effect.remove_old_periodic_effect_ticks()

            self.cast_end_timestamp -= pushback_length_sec
            data = pack('<I', int((remaining_cast_before_pushback - pushback_length_sec)*1000))  # *1000 for millis.

        elif self.cast_state == SpellState.SPELL_STATE_CASTING:
            final_opcode = OpCode.SMSG_SPELL_DELAYED
            cast_progress_seconds = self.get_base_cast_time()/1000 - remaining_cast_before_pushback  # base cast time in seconds.
            pushback_length_sec = min(cast_progress_seconds, 0.5)  # Push back 0.5s or to beginning of cast.

            self.cast_end_timestamp += pushback_length_sec
            data = pack('<QI', self.spell_caster.guid, int(pushback_length_sec * 1000))  # *1000 for millis.
        else:
            return

        MapManager.send_surrounding(PacketWriter.get_packet(final_opcode, data), self.spell_caster,
                                    include_self=self.spell_caster.get_type() == ObjectTypes.TYPE_PLAYER)
