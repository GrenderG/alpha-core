import time
from struct import pack

from database.dbc.DbcDatabaseManager import DbcDatabaseManager
from database.dbc.DbcModels import Spell, SpellCastTimes, SpellRange
from database.realm.RealmDatabaseManager import RealmDatabaseManager, CharacterSpell
from game.world.managers.GridManager import GridManager
from network.packet.PacketWriter import PacketWriter, OpCode
from utils.Logger import Logger
from utils.constants.SpellCodes import SpellCheckCastResult, SpellCastStatus, \
    SpellMissReason, SpellTargetMask, SpellState, SpellEffects, SpellTargetType, SpellAttributes


class CastingSpell(object):
    spell_entry: Spell
    cast_state: SpellState
    spell_caster = None
    initial_target_unit = None
    target_results: dict
    spell_target_mask: SpellTargetMask
    range_entry: SpellRange
    cast_time_entry: SpellCastTimes
    cast_end_timestamp: float
    spell_delay_end_timestamp: float

    def __init__(self, spell, caster_obj, initial_target_unit, target_results, target_mask):
        self.spell_entry = spell
        self.spell_caster = caster_obj
        self.initial_target_unit = initial_target_unit
        self.target_results = target_results
        self.spell_target_mask = target_mask
        self.range_entry = DbcDatabaseManager.spell_range_get_by_id(spell.RangeIndex)
        self.cast_time_entry = DbcDatabaseManager.spell_cast_time_get_by_id(spell.CastingTimeIndex)
        self.cast_end_timestamp = self.get_base_cast_time()/1000 + time.time()

        self.cast_state = SpellState.SPELL_STATE_PREPARING

    def is_instant_cast(self):
        return self.cast_time_entry.Base == 0

    def cast_on_swing(self):
        return self.spell_entry.Attributes & SpellAttributes.SPELL_ATTR_ON_NEXT_SWING_1 == SpellAttributes.SPELL_ATTR_ON_NEXT_SWING_1

    def get_base_cast_time(self):
        skill = self.spell_caster.skill_manager.get_skill_for_spell_id(self.spell_entry.ID)
        if not skill:
            return self.cast_time_entry.Minimum

        return int(max(self.cast_time_entry.Minimum, self.cast_time_entry.Base + self.cast_time_entry.PerLevel * skill.value))

    def get_effects(self):
        effects = []
        if self.spell_entry.Effect_1 != 0:
            effects.append(SpellEffect(self.spell_entry, 1))
        if self.spell_entry.Effect_2 != 0:
            effects.append(SpellEffect(self.spell_entry, 2))
        if self.spell_entry.Effect_3 != 0:
            effects.append(SpellEffect(self.spell_entry, 3))
        return effects

class SpellEffect(object):
    effect_type: SpellEffects
    die_sides: int
    base_dice: int
    dice_per_level: int
    real_points_per_level: int
    base_points: int
    implicit_target_a: SpellTargetType
    implicit_target_b: SpellTargetType
    radius_index: int
    aura_id: int
    aura_period: int
    amplitude: int
    chain_targets: int
    item_type: int
    misc_value: int
    trigger_spell: int

    def __init__(self, spell, index):
        if index == 1:
            self.load_first(spell)
        elif index == 2:
            self.load_second(spell)
        elif index == 3:
            self.load_third(spell)

    def load_first(self, spell):
        self.effect_type = spell.Effect_1
        self.die_sides = spell.EffectDieSides_1
        self.base_dice = spell.EffectBaseDice_1
        self.dice_per_level = spell.EffectDicePerLevel_1
        self.real_points_per_level = spell.EffectRealPointsPerLevel_1
        self.base_points = spell.EffectBasePoints_1
        self.implicit_target_a = spell.ImplicitTargetA_1
        self.implicit_target_b = spell.ImplicitTargetB_1
        self.radius_index = spell.EffectRadiusIndex_1
        self.aura_id = spell.EffectAura_1
        self.aura_period = spell.EffectAuraPeriod_1
        self.amplitude = spell.EffectAmplitude_1
        self.chain_targets = spell.EffectChainTargets_1
        self.item_type = spell.EffectItemType_1
        self.misc_value = spell.EffectMiscValue_1
        self.trigger_spell = spell.EffectTriggerSpell_1
        
    def load_second(self, spell):
        self.effect_type = spell.Effect_2
        self.die_sides = spell.EffectDieSides_2
        self.base_dice = spell.EffectBaseDice_2
        self.dice_per_level = spell.EffectDicePerLevel_2
        self.real_points_per_level = spell.EffectRealPointsPerLevel_2
        self.base_points = spell.EffectBasePoints_2
        self.implicit_target_a = spell.ImplicitTargetA_2
        self.implicit_target_b = spell.ImplicitTargetB_2
        self.radius_index = spell.EffectRadiusIndex_2
        self.aura_id = spell.EffectAura_2
        self.aura_period = spell.EffectAuraPeriod_2
        self.amplitude = spell.EffectAmplitude_2
        self.chain_targets = spell.EffectChainTargets_2
        self.item_type = spell.EffectItemType_2
        self.misc_value = spell.EffectMiscValue_2
        self.trigger_spell = spell.EffectTriggerSpell_2

    def load_third(self, spell):
        self.effect_type = spell.Effect_3
        self.die_sides = spell.EffectDieSides_3
        self.base_dice = spell.EffectBaseDice_3
        self.dice_per_level = spell.EffectDicePerLevel_3
        self.real_points_per_level = spell.EffectRealPointsPerLevel_3
        self.base_points = spell.EffectBasePoints_3
        self.implicit_target_a = spell.ImplicitTargetA_3
        self.implicit_target_b = spell.ImplicitTargetB_3
        self.radius_index = spell.EffectRadiusIndex_3
        self.aura_id = spell.EffectAura_3
        self.aura_period = spell.EffectAuraPeriod_3
        self.amplitude = spell.EffectAmplitude_3
        self.chain_targets = spell.EffectChainTargets_3
        self.item_type = spell.EffectItemType_3
        self.misc_value = spell.EffectMiscValue_3
        self.trigger_spell = spell.EffectTriggerSpell_3
    

class SpellEffectHandler(object):  # TODO implement die sides https://wowdev.wiki/DB/Spell
    @staticmethod
    def apply_effect(spell, effect, caster, unit):
        if effect.effect_type not in SPELL_EFFECTS:
            Logger.debug("Unimplemented effect called: " + str(effect.effect_type))
            return
        SPELL_EFFECTS[effect.effect_type](spell, effect, caster, unit)

    @staticmethod
    def handle_school_damage(spell, effect, caster, unit):
        damage = int(effect.base_points + effect.real_points_per_level * caster.level)
        caster.deal_spell_damage(unit, damage, spell.School, spell.ID)

    @staticmethod
    def handle_heal(spell, effect, caster, unit):
        healing = int(effect.base_points + effect.real_points_per_level * caster.level)

    @staticmethod
    def handle_weapon_damage(spell, effect, caster, unit):
        damage = int(caster.calculate_damage + effect.base_points)
        caster.deal_spell_damage(unit, damage, spell.School, spell.ID)

SPELL_EFFECTS = {
    SpellEffects.SPELL_EFFECT_SCHOOL_DAMAGE: SpellEffectHandler.handle_school_damage,
    SpellEffects.SPELL_EFFECT_HEAL: SpellEffectHandler.handle_heal,
    SpellEffects.SPELL_EFFECT_WEAPON_DAMAGE: SpellEffectHandler.handle_weapon_damage
}


class SpellManager(object):
    def __init__(self, player_mgr):
        self.player_mgr = player_mgr
        self.spells = {}
        self.cooldowns = {}
        self.casting_spells = []

    def load_spells(self):
        for spell in RealmDatabaseManager.character_get_spells(self.player_mgr.guid):
            self.spells[spell.spell] = spell

    def learn_spell(self, spell_id):
        spell = DbcDatabaseManager.SpellHolder.spell_get_by_id(spell_id)
        if not spell:
            return

        db_spell = CharacterSpell()
        db_spell.guid = self.player_mgr.guid
        db_spell.spell = spell_id
        RealmDatabaseManager.character_add_spell(db_spell)
        self.spells[spell_id] = db_spell

        data = pack('<H', spell_id)
        self.player_mgr.session.request.sendall(PacketWriter.get_packet(OpCode.SMSG_LEARNED_SPELL, data))
        # Teach skills required as well like in CharCreateHandler?

    def get_initial_spells(self):
        data = pack('<BH', 0, len(self.spells))
        for spell_id, spell in self.spells.items():
            data += pack('<2H', spell.spell, 0)
        data += pack('<H', 0)

        return PacketWriter.get_packet(OpCode.SMSG_INITIAL_SPELLS, data)

    def handle_cast_attempt(self, spell_id, caster, target_guid, target_mask):
        spell = DbcDatabaseManager.SpellHolder.spell_get_by_id(spell_id)
        if not spell:
            return
        spell_target = GridManager.get_surrounding_unit_by_guid(caster, target_guid) if target_guid and target_guid != caster.guid else caster
        self.start_spell_cast(spell, caster, spell_target, target_mask)

    def start_spell_cast(self, spell, caster_obj, spell_target, target_mask):
        targets = self.build_targets_for_spell(spell, spell_target, target_mask)
        casting_spell = CastingSpell(spell, caster_obj, spell_target, targets, target_mask)  # Initializes dbc references

        if not self.validate_cast(casting_spell):
            return

        if not casting_spell.is_instant_cast():
            self.send_cast_start(casting_spell)
            casting_spell.cast_state = SpellState.SPELL_STATE_CASTING
            self.casting_spells.append(casting_spell)
            return

        # Spell is instant, perform cast
        self.perform_spell_cast(casting_spell)

    def perform_spell_cast(self, casting_spell):
        self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_CAST_OK)
        self.send_spell_GO(casting_spell)

        travel_time = self.calculate_time_to_impact(casting_spell)
        if travel_time != 0:
            casting_spell.cast_state = SpellState.SPELL_STATE_DELAYED
            casting_spell.spell_delay_end_timestamp = time.time() + travel_time
            return
        elif casting_spell.cast_on_swing():
            casting_spell.cast_state = SpellState.SPELL_STATE_DELAYED
            # TODO send spell activate packet ??

        casting_spell.cast_state = SpellState.SPELL_STATE_FINISHED
        # self.send_channel_start(casting_spell.cast_time_entry.Base) TODO Only channeled spells

    has_moved = False

    def trigger_melee_swing(self):
        for casting_spell in self.casting_spells:
            if not casting_spell.cast_on_swing():
                continue
            for effect in casting_spell.get_effects():  # TODO check effect flags
                SpellEffectHandler.apply_effect(casting_spell.spell_entry, effect,
                                                casting_spell.spell_caster, casting_spell.initial_target_unit)
            self.remove_cast(casting_spell)

    def flag_as_moved(self):
        # TODO temporary way of handling this until movement data can be passed to update()
        if len(self.casting_spells) == 0:
            return
        self.has_moved = True

    def update(self, timestamp):
        moved = self.has_moved
        self.has_moved = False  # Reset has_moved on every update
        for casting_spell in list(self.casting_spells):
            if casting_spell.cast_state == SpellState.SPELL_STATE_CASTING:
                if casting_spell.cast_end_timestamp <= timestamp:
                    if not self.validate_cast(casting_spell):  # Spell finished casting, validate again
                        self.remove_cast(casting_spell)
                        return
                    self.perform_spell_cast(casting_spell)
                    if casting_spell.cast_state == SpellState.SPELL_STATE_FINISHED:  # Spell finished after perform (no impact delay)
                        self.remove_cast(casting_spell)
                elif moved:  # Spell has not finished casting, check movement
                    self.remove_cast(casting_spell, SpellCheckCastResult.SPELL_FAILED_MOVING)
                    self.has_moved = False
                    return

            elif casting_spell.cast_state == SpellState.SPELL_STATE_DELAYED and \
                    casting_spell.spell_delay_end_timestamp <= timestamp:  # Spell was cast already and impact delay is done
                for effect in casting_spell.get_effects():
                    SpellEffectHandler.apply_effect(casting_spell.spell_entry, effect,
                                                    casting_spell.spell_caster, casting_spell.initial_target_unit)
                self.remove_cast(casting_spell)

    def remove_cast(self, casting_spell, cast_result=SpellCheckCastResult.SPELL_CAST_OK):
        if casting_spell not in self.casting_spells:
            return
        self.casting_spells.remove(casting_spell)
        if cast_result != SpellCheckCastResult.SPELL_CAST_OK:
            self.send_cast_result(casting_spell.spell_entry.ID, cast_result)


    def calculate_time_to_impact(self, casting_spell):
        if casting_spell.spell_entry.Speed == 0:
            return 0

        travel_distance = casting_spell.range_entry.RangeMax
        if casting_spell.spell_target_mask & SpellTargetMask.UNIT == SpellTargetMask.UNIT:
            target_unit_location = casting_spell.initial_target_unit.location
            travel_distance = casting_spell.spell_caster.location.distance(target_unit_location)

        return travel_distance / casting_spell.spell_entry.Speed

    def build_targets_for_spell(self, spell, target, target_mask):
        if target_mask == SpellTargetMask.SELF or target is None:
            return {}
        return {target.guid: SpellMissReason.MISS_REASON_NONE}

    def send_cast_start(self, casting_spell):
        data = [self.player_mgr.guid, self.player_mgr.guid,
                casting_spell.spell_entry.ID, 0, casting_spell.get_base_cast_time(),
                casting_spell.spell_target_mask]

        signature = "<QQIHiH"  # TODO
        if casting_spell.initial_target_unit:
            data.append(casting_spell.initial_target_unit.guid)
            signature += "Q"

        data = pack(signature, *data)
        Logger.debug("sending cast start of spell " + casting_spell.spell_entry.Name_enUS + " with cast time " + str(casting_spell.get_base_cast_time()))

        # TODO send surrounding probably
        self.player_mgr.session.request.sendall(PacketWriter.get_packet(OpCode.SMSG_SPELL_START, data))

    def send_spell_GO(self, casting_spell):
        data = [self.player_mgr.guid, self.player_mgr.guid,
                casting_spell.spell_entry.ID, 0]  # TODO Flags

        sign = "<QQIH"

        hit_count = 0
        if len(casting_spell.target_results.keys()) > 0:
            hit_count += 1
        sign += 'B'
        data.append(hit_count)

        for target, reason in casting_spell.target_results.items():
            if reason == SpellMissReason.MISS_REASON_NONE:
                data.append(target)
                sign += 'Q'

        data.append(0)  # miss count
        sign += 'B'

        sign += 'H'  # SpellTargetMask
        data.append(casting_spell.spell_target_mask)

        # write initial target
        if casting_spell.spell_target_mask & SpellTargetMask.UNIT == SpellTargetMask.UNIT:
            sign += 'Q'
            data.append(casting_spell.initial_target_unit.guid)

        #data = pack("QQIHBBH", self.player_mgr.guid, self.player_mgr.guid,
        #            casting_spell.spell_entry.ID, 0,
        #            0, 0,  # Hit targets count, miss targets count
        #            0,   # SpellTargetMask - 0 for self
        #            )

        packed = pack(sign, *data)
        self.player_mgr.session.request.sendall(PacketWriter.get_packet(OpCode.SMSG_SPELL_GO, packed))

    def set_on_cooldown(self, spell):
        self.cooldowns[spell.ID] = spell.RecoveryTime + time.time()

        data = pack('<IQH', spell.ID, self.player_mgr.guid, spell.RecoveryTime)
        self.player_mgr.session.request.sendall(PacketWriter.get_packet(OpCode.SMSG_SPELL_COOLDOWN, data))

    def is_on_cooldown(self, spell_id):
        return spell_id in self.cooldowns

    def validate_cast(self, casting_spell):
        if not casting_spell.spell_entry or casting_spell.spell_entry.ID not in self.spells:
            self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_NOT_KNOWN)
            return False

        if not casting_spell.initial_target_unit:
            self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_BAD_TARGETS)
            return False

        if not casting_spell.initial_target_unit or not casting_spell.initial_target_unit.is_alive:
            self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_TARGETS_DEAD)
            return False

        if self.has_moved:
            self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_MOVING)
            return False
        return True

    def send_cast_result(self, spell_id, error):
        # cast_status = SpellCastStatus.CAST_SUCCESS if error == SpellCheckCastResult.SPELL_CAST_OK else SpellCastStatus.CAST_FAILED  # TODO CAST_SUCCESS_KEEP_TRACKING
        if error == SpellCheckCastResult.SPELL_CAST_OK:
            data = pack('<IB', spell_id, SpellCastStatus.CAST_SUCCESS)
        else:
            data = pack('<IBB', spell_id, SpellCastStatus.CAST_FAILED, error)
        self.player_mgr.session.request.sendall(PacketWriter.get_packet(OpCode.SMSG_CAST_RESULT, data))
