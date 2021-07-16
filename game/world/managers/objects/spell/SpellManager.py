import time
from struct import pack
from typing import Optional

from database.dbc.DbcDatabaseManager import DbcDatabaseManager
from database.realm.RealmDatabaseManager import RealmDatabaseManager, CharacterSpell
from database.world.WorldDatabaseManager import WorldDatabaseManager
from game.world.managers.abstractions.Vector import Vector
from game.world.managers.maps.MapManager import MapManager
from game.world.managers.objects.ObjectManager import ObjectManager
from game.world.managers.objects.spell.CastingSpell import CastingSpell
from game.world.managers.objects.spell.CooldownEntry import CooldownEntry
from game.world.managers.objects.spell.SpellEffectHandler import SpellEffectHandler
from network.packet.PacketWriter import PacketWriter, OpCode
from utils.Logger import Logger
from utils.constants.ItemCodes import InventoryError, InventoryTypes
from utils.constants.MiscCodes import ObjectTypes, HitInfo
from utils.constants.SpellCodes import SpellCheckCastResult, SpellCastStatus, \
    SpellMissReason, SpellTargetMask, SpellState, SpellAttributes, SpellCastFlags, SpellEffects, SpellSchools, \
    SpellInterruptFlags, SpellChannelInterruptFlags, SpellAttributesEx
from utils.constants.UnitCodes import PowerTypes, StandState


class SpellManager(object):
    def __init__(self, unit_mgr):
        self.unit_mgr = unit_mgr
        self.spells = {}
        self.cooldowns = []
        self.casting_spells = []

    def load_spells(self):
        for spell in RealmDatabaseManager.character_get_spells(self.unit_mgr.guid):
            self.spells[spell.spell] = spell

    def learn_spell(self, spell_id, cast_on_learn=False) -> bool:
        if self.unit_mgr.get_type() != ObjectTypes.TYPE_PLAYER:
            return False

        spell = DbcDatabaseManager.SpellHolder.spell_get_by_id(spell_id)
        if not spell:
            return False

        if spell_id in self.spells:
            return False

        db_spell = CharacterSpell()
        db_spell.guid = self.unit_mgr.guid
        db_spell.spell = spell_id
        RealmDatabaseManager.character_add_spell(db_spell)
        self.spells[spell_id] = db_spell

        data = pack('<H', spell_id)
        self.unit_mgr.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_LEARNED_SPELL, data))

        if cast_on_learn or spell.AttributesEx & SpellAttributesEx.SPELL_ATTR_EX_CAST_WHEN_LEARNED:
            self.start_spell_cast(spell, self.unit_mgr, self.unit_mgr, SpellTargetMask.SELF)

        # Teach skill required as well like in CharCreateHandler?
        return True

    def get_initial_spells(self) -> bytes:
        spell_buttons = RealmDatabaseManager.character_get_spell_buttons(self.unit_mgr.guid)
        
        data = pack('<BH', 0, len(self.spells))
        for spell_id, spell in self.spells.items():
            index = spell_buttons[spell.spell] if spell.spell in spell_buttons else 0
            data += pack('<2h', spell.spell, index)
        data += pack('<H', 0)

        return PacketWriter.get_packet(OpCode.SMSG_INITIAL_SPELLS, data)

    def handle_item_cast_attempt(self, item, caster):
        for spell_info in item.spell_stats:
            if spell_info.spell_id == 0:
                break
            spell = DbcDatabaseManager.SpellHolder.spell_get_by_id(spell_info.spell_id)
            if not spell:
                Logger.warning(f'Spell {spell_info.spell_id} tied to item {item.item_template.entry} ({item.item_template.name}) could not be found in the spell database.')
                continue

            casting_spell = self.try_initialize_spell(spell, caster, caster, SpellTargetMask.SELF, item)  # TODO item spells targeting others?
            if not casting_spell:
                continue
            if casting_spell.is_refreshment_spell():  # Food/drink items don't send sit packet - handle here
                caster.set_stand_state(StandState.UNIT_SITTING)

            self.start_spell_cast(spell, caster, caster, SpellTargetMask.SELF, item)

    def handle_cast_attempt(self, spell_id, caster, spell_target, target_mask):
        spell = DbcDatabaseManager.SpellHolder.spell_get_by_id(spell_id)
        if not spell or not spell_target:
            return

        self.start_spell_cast(spell, caster, spell_target, target_mask)

    def try_initialize_spell(self, spell, caster_obj, spell_target, target_mask, source_item=None, validate=True) -> Optional[CastingSpell]:
        spell = CastingSpell(spell, caster_obj, spell_target, target_mask, source_item)
        if not validate:
            return spell
        return spell if self.validate_cast(spell) else None

    def start_spell_cast(self, spell, caster, spell_target, target_mask, source_item=None,
                         initialized_spell=None, is_trigger=False):
        casting_spell = self.try_initialize_spell(spell, caster, spell_target, target_mask, source_item) if not initialized_spell else initialized_spell
        if not casting_spell:
            return

        if not is_trigger:
            self.remove_colliding_casts(casting_spell)
        else:
            casting_spell.cast_flags |= SpellCastFlags.CAST_FLAG_PROC

        casting_spell.cast_start_timestamp = time.time()

        if casting_spell.casts_on_swing():  # Handle swing ability queue and state
            casting_spell.cast_state = SpellState.SPELL_STATE_DELAYED  # Wait for next swing
            self.casting_spells.append(casting_spell)
            return

        self.casting_spells.append(casting_spell)
        casting_spell.cast_state = SpellState.SPELL_STATE_CASTING

        if not casting_spell.is_instant_cast():
            self.send_cast_start(casting_spell)
            return

        # Spell is instant, perform cast
        self.perform_spell_cast(casting_spell, validate=False, is_trigger=is_trigger)

    def perform_spell_cast(self, casting_spell, validate=True, is_trigger=False):
        if validate and not self.validate_cast(casting_spell):
            self.remove_cast(casting_spell)
            return

        casting_spell.resolve_target_info_for_effects()

        if casting_spell.cast_state == SpellState.SPELL_STATE_DELAYED:
            return  # Spell is in delayed state, do nothing for now

        self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_NO_ERROR)
        self.send_spell_go(casting_spell)

        if not is_trigger:  # Triggered spells (ie. channel ticks) shouldn't interrupt other casts
            self.unit_mgr.aura_manager.check_aura_interrupts(cast_spell=True)

        travel_times = self.calculate_impact_delays(casting_spell)

        if len(travel_times) != 0:
            casting_spell.spell_impact_timestamps = {}
            curr_time = time.time()

            for guid, delay in travel_times.items():
                casting_spell.spell_impact_timestamps[guid] = curr_time + delay

            casting_spell.cast_state = SpellState.SPELL_STATE_DELAYED
            self.consume_resources_for_cast(casting_spell)  # Remove resources
            return

        casting_spell.cast_state = SpellState.SPELL_STATE_FINISHED
        if casting_spell.is_channeled():
            self.handle_channel_start(casting_spell)  # Channeled spells require more setup before effect application
        else:
            self.apply_spell_effects(casting_spell)  # Apply effects
            # Some spell effect handlers will set the spell state to active as the handler needs to be called on updates
            if casting_spell.cast_state != SpellState.SPELL_STATE_ACTIVE:
                self.remove_cast(casting_spell)

        self.set_on_cooldown(casting_spell)

        self.consume_resources_for_cast(casting_spell)  # Remove resources - order matters for combo points

    def apply_spell_effects(self, casting_spell, remove=False, update=False, partial_targets=None):
        if not update:
            self.handle_procs_for_cast(casting_spell)

        for effect in casting_spell.effects:
            if not update:
                effect.handle_application()

            if effect.effect_type in SpellEffectHandler.AREA_SPELL_EFFECTS:
                SpellEffectHandler.apply_effect(casting_spell, effect, casting_spell.spell_caster, None)
                continue

            object_targets = effect.targets.get_resolved_effect_targets_by_type(ObjectManager)

            for target in object_targets:
                if partial_targets and target.guid not in partial_targets:
                    continue
                info = casting_spell.object_target_results[target.guid]
                # TODO deflection handling? Swap target/caster for now
                if info.result == SpellMissReason.MISS_REASON_DEFLECTED:
                    SpellEffectHandler.apply_effect(casting_spell, effect, info.target, casting_spell.spell_caster)
                elif info.result == SpellMissReason.MISS_REASON_NONE:
                    SpellEffectHandler.apply_effect(casting_spell, effect, casting_spell.spell_caster, info.target)

            if len(object_targets) > 0:
                continue  # Prefer unit target for handling (don't attempt to resolve other target types for one effect if unit targets aren't empty)

            for target in effect.targets.get_resolved_effect_targets_by_type(Vector):
                SpellEffectHandler.apply_effect(casting_spell, effect, casting_spell.spell_caster, target)

        if remove:
            self.remove_cast(casting_spell)

    def handle_procs_for_cast(self, casting_spell):
        applied_targets = []
        for effect in casting_spell.effects:
            for target in effect.targets.get_resolved_effect_targets_by_type(ObjectManager):
                if target.guid in applied_targets:
                    continue

                target_info = casting_spell.object_target_results[target.guid]
                if target_info.result != SpellMissReason.MISS_REASON_NONE:
                    continue
                if ObjectTypes.TYPE_UNIT in target.object_type:
                    target.aura_manager.check_aura_procs(involved_cast=casting_spell)
                casting_spell.spell_caster.aura_manager.check_aura_procs(involved_cast=casting_spell)
                applied_targets.append(target.guid)

    def cast_queued_melee_ability(self, attack_type) -> bool:
        melee_ability = self.get_queued_melee_ability()

        if not melee_ability or not self.validate_cast(melee_ability):
            self.remove_cast(melee_ability)
            return False

        melee_ability.spell_attack_type = attack_type

        melee_ability.cast_state = SpellState.SPELL_STATE_CASTING
        self.perform_spell_cast(melee_ability, False)
        return True

    def get_queued_melee_ability(self) -> Optional[CastingSpell]:
        for casting_spell in self.casting_spells:
            if not casting_spell.casts_on_swing() or \
                    casting_spell.cast_state != SpellState.SPELL_STATE_DELAYED:
                continue
            return casting_spell
        return None

    has_moved = False

    def flag_as_moved(self):
        # TODO temporary way of handling this until movement data can be passed to update()
        self.unit_mgr.aura_manager.has_moved = True
        if len(self.casting_spells) == 0:
            return
        self.has_moved = True

    def update(self, timestamp, elapsed):
        moved = self.has_moved
        self.has_moved = False  # Reset has_moved on every update
        self.check_spell_cooldowns()
        self.check_spell_interrupts(moved=moved)
        for casting_spell in list(self.casting_spells):
            if casting_spell.casts_on_swing():  # spells cast on swing will be updated on call from attack handling
                continue
            cast_finished = casting_spell.cast_end_timestamp <= timestamp
            if casting_spell.cast_state == SpellState.SPELL_STATE_ACTIVE:  # Channel tick/spells that need updates
                self.handle_spell_effect_update(casting_spell, timestamp)  # Update effects if the cast wasn't interrupted

                if casting_spell.is_channeled() and cast_finished:
                    self.remove_cast(casting_spell)
                continue

            if casting_spell.cast_state == SpellState.SPELL_STATE_CASTING and not casting_spell.is_instant_cast():
                if cast_finished:
                    self.perform_spell_cast(casting_spell)
                    if casting_spell.cast_state == SpellState.SPELL_STATE_FINISHED:  # Spell finished after perform (no impact delay)
                        self.remove_cast(casting_spell)

            if casting_spell.cast_state == SpellState.SPELL_STATE_DELAYED:  # Waiting for impact delay
                targets_due = [guid for guid, stamp in casting_spell.spell_impact_timestamps.items() if stamp <= timestamp]
                if not targets_due:
                    continue

                for target in targets_due:
                    casting_spell.spell_impact_timestamps.pop(target)

                if len(casting_spell.spell_impact_timestamps) == 0:  # All targets finished impact delay.
                    self.apply_spell_effects(casting_spell, remove=True, partial_targets=targets_due)
                    continue

                # Only some targets finished delay
                self.apply_spell_effects(casting_spell, partial_targets=targets_due)

    def check_spell_interrupts(self, moved=False, turned=False, received_damage=False, hit_info=HitInfo.DAMAGE,
                               interrupted=False, received_auto_attack=False):  # TODO provide interrupted, turned
        casting_spell_flag_cases = {
            SpellInterruptFlags.SPELL_INTERRUPT_FLAG_MOVEMENT: moved,
            SpellInterruptFlags.SPELL_INTERRUPT_FLAG_DAMAGE: received_damage,
            SpellInterruptFlags.SPELL_INTERRUPT_FLAG_INTERRUPT: interrupted,
            SpellInterruptFlags.SPELL_INTERRUPT_FLAG_AUTOATTACK: received_auto_attack,
        }
        channeling_spell_flag_cases = {
            SpellChannelInterruptFlags.CHANNEL_INTERRUPT_FLAG_DAMAGE: received_damage,
            SpellChannelInterruptFlags.CHANNEL_INTERRUPT_FLAG_MOVEMENT: moved,
            SpellChannelInterruptFlags.CHANNEL_INTERRUPT_FLAG_TURNING: turned,
            SpellChannelInterruptFlags.CHANNEL_INTERRUPT_FLAG_FULL_INTERRUPT: received_auto_attack

        }
        for casting_spell in list(self.casting_spells):
            if casting_spell.cast_state == SpellState.SPELL_STATE_DELAYED:
                continue

            if casting_spell.is_channeled() and casting_spell.cast_state == SpellState.SPELL_STATE_ACTIVE:
                for flag, condition in channeling_spell_flag_cases.items():
                    channel_flags = casting_spell.spell_entry.ChannelInterruptFlags
                    if not (channel_flags & flag) or not condition:
                        continue

                    # TODO Do crushing blows interrupt channeling too?
                    if not (channel_flags & SpellChannelInterruptFlags.CHANNEL_INTERRUPT_FLAG_FULL_INTERRUPT) and hit_info != HitInfo.CRUSHING and \
                            flag != SpellChannelInterruptFlags.CHANNEL_INTERRUPT_FLAG_MOVEMENT:
                        casting_spell.handle_partial_interrupt()
                    else:
                        self.remove_cast(casting_spell, SpellCheckCastResult.SPELL_FAILED_INTERRUPTED, interrupted=True)
                continue

            for flag, condition in casting_spell_flag_cases.items():
                spell_flags = casting_spell.spell_entry.InterruptFlags
                if not (spell_flags & flag) or not condition:
                    continue

                # - Creatures dealing enough damage (crushing blow) will now fully interrupt casting. (0.5.3 notes).
                if spell_flags & SpellInterruptFlags.SPELL_INTERRUPT_FLAG_PARTIAL and hit_info != HitInfo.CRUSHING and \
                        flag != SpellInterruptFlags.SPELL_INTERRUPT_FLAG_MOVEMENT:
                    casting_spell.handle_partial_interrupt()
                else:
                    self.remove_cast(casting_spell, SpellCheckCastResult.SPELL_FAILED_INTERRUPTED, interrupted=True)

    def remove_cast(self, casting_spell, cast_result=SpellCheckCastResult.SPELL_NO_ERROR, interrupted=False):
        if casting_spell not in self.casting_spells:
            return

        self.casting_spells.remove(casting_spell)

        # Cancel auras applied by an active spell if the spell was interrupted.
        # If the cast finished normally, auras should wear off because of duration.
        # Since spell update happens before aura update, last ticks will be skipped if auras are cancelled on cast finish.
        if casting_spell.cast_state == SpellState.SPELL_STATE_ACTIVE and interrupted:
            for miss_info in casting_spell.object_target_results.values():  # Get the last effect application results.
                if ObjectTypes.TYPE_UNIT not in miss_info.target.object_type:
                    continue
                miss_info.target.aura_manager.cancel_auras_by_spell_id(casting_spell.spell_entry.ID)  # Cancel effects from this aura.

        if casting_spell.is_channeled():
            self.handle_channel_end(casting_spell)

        if cast_result != SpellCheckCastResult.SPELL_NO_ERROR:
            self.send_cast_result(casting_spell.spell_entry.ID, cast_result)

    def remove_cast_by_id(self, spell_id, interrupted=False):
        for casting_spell in list(self.casting_spells):
            if spell_id != casting_spell.spell_entry.ID:
                continue
            self.remove_cast(casting_spell, SpellCheckCastResult.SPELL_FAILED_INTERRUPTED, interrupted)

    def remove_all_casts(self, cast_result=SpellCheckCastResult.SPELL_NO_ERROR):
        for casting_spell in list(self.casting_spells):
            result = SpellCheckCastResult.SPELL_FAILED_INTERRUPTED
            if not casting_spell.is_channeled() and casting_spell.cast_state == SpellState.SPELL_STATE_ACTIVE or \
                    casting_spell.cast_state == SpellState.SPELL_STATE_DELAYED:
                result = SpellCheckCastResult.SPELL_NO_ERROR  # Don't send interrupted error for active/delayed spells

            self.remove_cast(casting_spell, result, interrupted=True)

    def remove_unit_from_all_cast_targets(self, target_guid):
        for casting_spell in list(self.casting_spells):
            if not casting_spell.initial_target_is_unit_or_player() or (casting_spell.is_instant_cast() and not casting_spell.is_channeled()):  # Don't interrupt instant casts
                continue

            if target_guid in casting_spell.object_target_results and len(casting_spell.object_target_results) == 1:  # Only target of this spell
                result = SpellCheckCastResult.SPELL_FAILED_INTERRUPTED
                if not casting_spell.is_channeled() and casting_spell.cast_state == SpellState.SPELL_STATE_ACTIVE or \
                        casting_spell.cast_state == SpellState.SPELL_STATE_DELAYED:
                    result = SpellCheckCastResult.SPELL_NO_ERROR  # Don't send interrupted error for active/delayed spells

                self.remove_cast(casting_spell, result, interrupted=True)
                return

            for effect in casting_spell.effects:
                effect.targets.remove_object_from_targets(target_guid)

    def remove_colliding_casts(self, current_cast):
        for casting_spell in self.casting_spells:
            if casting_spell.cast_state == SpellState.SPELL_STATE_CASTING or casting_spell.is_channeled():
                self.remove_cast(casting_spell, SpellCheckCastResult.SPELL_FAILED_INTERRUPTED, interrupted=True)
                continue
            if casting_spell.is_paladin_aura() and current_cast.is_paladin_aura():  # Paladin aura exclusivity.
                self.remove_cast(casting_spell, interrupted=True)
                continue
            if current_cast.casts_on_swing() and casting_spell.casts_on_swing() and casting_spell.cast_state == SpellState.SPELL_STATE_DELAYED:
                self.remove_cast(casting_spell, interrupted=True)
                continue

    def calculate_impact_delays(self, casting_spell) -> dict[int, float]:
        impact_delays = {}
        if casting_spell.spell_entry.Speed == 0:
            return impact_delays

        lowest_delay = 0
        for effect in casting_spell.effects:
            vector_targets = effect.targets.get_resolved_effect_targets_by_type(Vector)
            if len(vector_targets) > 0:  # Throwable items - bombs etc. Set as the minimum delay for unit targets.
                travel_distance = vector_targets[0].distance(effect.targets.effect_source)
                lowest_delay = travel_distance / casting_spell.spell_entry.Speed

            unit_targets = effect.targets.get_resolved_effect_targets_by_type(ObjectManager)
            source = effect.targets.effect_source
            for target in unit_targets:
                if casting_spell.spell_impact_timestamps.get(target.guid, None) == -1:
                    # Instant target handlers should write -1 to timestamps.
                    # In these cases, assign the lowest impact delay to the target to still account for regular impact delay.
                    impact_delays[target.guid] = -1
                    continue

                target_unit_location = target.location
                travel_distance = source.location.distance(target_unit_location)
                delay = travel_distance / casting_spell.spell_entry.Speed
                if delay == 0:
                    continue
                impact_delays[target.guid] = delay
                lowest_delay = delay if delay < lowest_delay or lowest_delay == 0 else lowest_delay

        for guid, delay in impact_delays.items():
            impact_delays[guid] = lowest_delay if delay == -1 else delay

        return impact_delays

    def send_cast_start(self, casting_spell):
        data = [self.unit_mgr.guid, self.unit_mgr.guid,  # TODO Source (1st arg) can also be item
                casting_spell.spell_entry.ID, casting_spell.cast_flags, casting_spell.get_base_cast_time(),
                casting_spell.spell_target_mask]

        signature = '<2QIHiH'  # source, caster, ID, flags, delay .. (targets, opt. ammo displayID / inventorytype).

        if casting_spell.initial_target and casting_spell.spell_target_mask != SpellTargetMask.SELF:  # Some self-cast spells crash client if target is written.
            target_info = casting_spell.get_initial_target_info()  # ([values], signature)
            data.extend(target_info[0])
            signature += target_info[1]

        if casting_spell.cast_flags & SpellCastFlags.CAST_FLAG_HAS_AMMO:
            signature += '2I'
            data.append(5996)  # TODO ammo display ID
            data.append(InventoryTypes.AMMO)  # TODO ammo inventorytype (thrown too)

        data = pack(signature, *data)
        MapManager.send_surrounding(PacketWriter.get_packet(OpCode.SMSG_SPELL_START, data), self.unit_mgr,
                                    include_self=self.unit_mgr.get_type() == ObjectTypes.TYPE_PLAYER)

    def handle_channel_start(self, casting_spell):
        if not casting_spell.is_channeled() or casting_spell.duration_entry.Duration == -1:
            return
        casting_spell.cast_state = SpellState.SPELL_STATE_ACTIVE
        channel_end_timestamp = casting_spell.duration_entry.Duration/1000 + time.time()
        casting_spell.cast_start_timestamp = time.time()
        casting_spell.cast_end_timestamp = channel_end_timestamp  # Set the new timestamp for cast finish.

        if casting_spell.initial_target_is_object():
            self.unit_mgr.set_channel_object(casting_spell.initial_target.guid)
        self.unit_mgr.set_channel_spell(casting_spell.spell_entry.ID)
        self.unit_mgr.set_dirty()

        self.apply_spell_effects(casting_spell)

        if self.unit_mgr.get_type() != ObjectTypes.TYPE_PLAYER:
            return

        data = pack('<2I', casting_spell.spell_entry.ID, casting_spell.duration_entry.Duration)  # No channeled spells with duration per level.
        self.unit_mgr.session.enqueue_packet(PacketWriter.get_packet(OpCode.MSG_CHANNEL_START, data))
        # TODO Channeling animations do not play

    def handle_spell_effect_update(self, casting_spell, timestamp):
        for effect in casting_spell.effects:
            # Refresh targets.
            casting_spell.resolve_target_info_for_effect(effect.effect_index)

            effect.remove_old_periodic_effect_ticks()

            # Update periodic effects.
            effect.update_effect_aura(timestamp)

            # Area spell effect update.
            if effect.effect_type in SpellEffectHandler.AREA_SPELL_EFFECTS:
                self.apply_spell_effects(casting_spell, update=True)

    def handle_channel_end(self, casting_spell):
        if not casting_spell.is_channeled():
            return

        if self.unit_mgr.get_type() != ObjectTypes.TYPE_PLAYER:
            return

        self.unit_mgr.set_channel_object(0)
        self.unit_mgr.set_channel_spell(0)
        self.unit_mgr.set_dirty()

        if self.unit_mgr.get_type() != ObjectTypes.TYPE_PLAYER:
            return

        data = pack('<I', 0)
        self.unit_mgr.session.enqueue_packet(PacketWriter.get_packet(OpCode.MSG_CHANNEL_UPDATE, data))

    def send_spell_go(self, casting_spell):
        data = [self.unit_mgr.guid, self.unit_mgr.guid,
                casting_spell.spell_entry.ID, casting_spell.cast_flags]

        signature = '<2QIH'  # source, caster, ID, flags .. (targets, ammo info).

        # Prepare target data
        results_by_type = {SpellMissReason.MISS_REASON_NONE: []}  # Hits need to be written first.

        # Only include the primary effect targets.
        targets = casting_spell.effects[0].targets.get_resolved_effect_targets_by_type(ObjectManager)
        for target in targets:
            miss_info = casting_spell.object_target_results[target.guid]
            new_targets = results_by_type.get(miss_info.result, [])
            new_targets.append(target.guid)
            results_by_type[miss_info.result] = new_targets  # Sort targets by hit type for filling packet fields.

        hit_count = len(results_by_type[SpellMissReason.MISS_REASON_NONE])
        miss_count = len(targets) - hit_count  # Subtract hits from all targets.
        # Write targets, hits first
        for result, guids in results_by_type.items():
            if result == SpellMissReason.MISS_REASON_NONE:  # Hit count is written separately.
                signature += 'B'
                data.append(hit_count)

            if result != SpellMissReason.MISS_REASON_NONE:  # Write reason for miss.
                signature += 'B'
                data.append(result)

            if len(guids) > 0:  # Write targets if there are any
                signature += f'{len(guids)}Q'
            for target_guid in guids:
                data.append(target_guid)

            if result == SpellMissReason.MISS_REASON_NONE:  # Write miss count at the end of hits since it needs to be written even if none happen.
                signature += 'B'
                data.append(miss_count)

        signature += 'H'  # SpellTargetMask
        data.append(casting_spell.spell_target_mask)

        if casting_spell.spell_target_mask != SpellTargetMask.SELF:  # Write target info - same as cast start.
            target_info = casting_spell.get_initial_target_info()  # ([values], signature)
            data.extend(target_info[0])
            signature += target_info[1]

        packed = pack(signature, *data)
        MapManager.send_surrounding(PacketWriter.get_packet(OpCode.SMSG_SPELL_GO, packed), self.unit_mgr,
                                    include_self=self.unit_mgr.get_type() == ObjectTypes.TYPE_PLAYER)

    def set_on_cooldown(self, casting_spell, start_locked_cooldown=False):
        spell = casting_spell.spell_entry

        if spell.RecoveryTime == 0 and spell.CategoryRecoveryTime == 0:
            return

        timestamp = time.time()

        if start_locked_cooldown:
            data = pack('<IQ', spell.ID, self.unit_mgr.guid)
            self.unit_mgr.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_COOLDOWN_EVENT, data))
            for cooldown in self.cooldowns:
                if cooldown.spell_id == spell.ID:
                    cooldown.unlock(timestamp)
                    return
            Logger.warning(f'[SpellManager]: Attempted to unlock cooldown for spell {spell.ID}, but the cooldown didn\'t exist.')

        cooldown_entry = CooldownEntry(spell, timestamp, casting_spell.trigger_cooldown_on_aura_remove())
        self.cooldowns.append(cooldown_entry)

        if self.unit_mgr.get_type() != ObjectTypes.TYPE_PLAYER:
            return

        data = pack('<IQI', spell.ID, self.unit_mgr.guid, cooldown_entry.cooldown_length)
        self.unit_mgr.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_SPELL_COOLDOWN, data))

    def check_spell_cooldowns(self):
        for cooldown_entry in list(self.cooldowns):
            if cooldown_entry.is_valid():
                continue

            self.cooldowns.remove(cooldown_entry)
            if self.unit_mgr.get_type() != ObjectTypes.TYPE_PLAYER:
                continue
            data = pack('<IQ', cooldown_entry.spell_id, self.unit_mgr.guid)
            self.unit_mgr.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_CLEAR_COOLDOWN, data))

    def is_on_cooldown(self, spell_entry) -> bool:
        for cooldown_entry in list(self.cooldowns):
            if cooldown_entry.is_valid() and cooldown_entry.matches_spell(spell_entry):
                return True
        return False

    def is_casting(self):
        for spell in list(self.casting_spells):
            if spell.cast_state == SpellState.SPELL_STATE_CASTING or \
                    (spell.is_channeled() and spell.cast_state == SpellState.SPELL_STATE_ACTIVE):
                return True
        return False

    def validate_cast(self, casting_spell) -> bool:
        if self.is_on_cooldown(casting_spell.spell_entry):
            self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_NOT_READY)
            return False

        if not casting_spell.source_item and self.unit_mgr.get_type() == ObjectTypes.TYPE_PLAYER and \
                (not casting_spell.spell_entry or casting_spell.spell_entry.ID not in self.spells):
            self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_NOT_KNOWN)
            return False

        if not self.unit_mgr.is_alive and \
                casting_spell.spell_entry.Attributes & SpellAttributes.SPELL_ATTR_ALLOW_CAST_WHILE_DEAD != SpellAttributes.SPELL_ATTR_ALLOW_CAST_WHILE_DEAD:
            self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_CASTER_DEAD)
            return False

        if not casting_spell.initial_target:
            self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_BAD_TARGETS)
            return False

        # Channeled spells that require persistent targets.
        if casting_spell.spell_entry.AttributesEx & SpellAttributesEx.SPELL_ATTR_EX_CHANNEL_TRACK_TARGET:
            if not casting_spell.targeted_unit_on_cast_start:
                self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_BAD_IMPLICIT_TARGETS)  # Arcane missiles cast only sends self as target but expects an unit target to track
                return False
            if not casting_spell.spell_caster.can_attack_target(casting_spell.targeted_unit_on_cast_start) and casting_spell.requires_hostile_target():
                self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_BAD_IMPLICIT_TARGETS)
                return False

        if casting_spell.initial_target_is_unit_or_player() and not casting_spell.initial_target.is_alive:  # TODO dead targets (resurrect)
            self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_TARGETS_DEAD)
            return False

        if not casting_spell.spell_entry.Attributes & SpellAttributes.SPELL_ATTR_CASTABLE_WHILE_SITTING and \
                self.unit_mgr.stand_state != StandState.UNIT_STANDING:
            self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_NOTSTANDING)

        if not self.meets_casting_requisites(casting_spell):
            return False

        return True

    def meets_casting_requisites(self, casting_spell) -> bool:
        has_health_cost = casting_spell.spell_entry.PowerType == PowerTypes.TYPE_HEALTH
        if not has_health_cost and casting_spell.spell_entry.PowerType != self.unit_mgr.power_type and \
                casting_spell.spell_entry.ManaCost != 0:  # Doesn't have the correct power type.
            self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_NO_POWER)
            return False

        current_power = self.unit_mgr.health if has_health_cost else self.unit_mgr.get_power_type_value()
        if casting_spell.get_resource_cost() > current_power:  # Doesn't have enough power
            if not has_health_cost:
                self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_NO_POWER)
            else:
                self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_NO_ERROR)  # Health cost fail displays on client before server response
            return False

        # Player only checks
        if self.unit_mgr.get_type() == ObjectTypes.TYPE_PLAYER:
            # Check if player has required combo points.
            if casting_spell.requires_combo_points() and \
                    (casting_spell.initial_target.guid != self.unit_mgr.combo_target or self.unit_mgr.combo_points == 0):  # Doesn't have required combo points.
                self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_NO_COMBO_POINTS)
                return False

            # Check if player has required reagents.
            for reagent_info, count in casting_spell.get_reagents():
                if reagent_info == 0:
                    break

                if self.unit_mgr.inventory.get_item_count(reagent_info) < count:
                    self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_REAGENTS)
                    return False

            # Spells cast with consumables.
            if casting_spell.source_item and casting_spell.source_item.has_charges():
                spell_stats = casting_spell.get_item_spell_stats()
                charges = spell_stats.charges
                if charges == 0:  # no charges left.
                    self.send_cast_result(casting_spell.spell_entry.ID,
                                          SpellCheckCastResult.SPELL_FAILED_NO_CHARGES_REMAIN)
                    return False
                if charges < 0 and self.unit_mgr.inventory.get_item_count(casting_spell.source_item.item_template.entry) < 1:  # Consumables have negative charges.
                    self.send_cast_result(casting_spell.spell_entry.ID,
                                          SpellCheckCastResult.SPELL_FAILED_ITEM_NOT_FOUND)  # Should never really happen but catch this case.
                    return False

            for tool in casting_spell.get_required_tools():
                if not tool:
                    break
                if not self.unit_mgr.inventory.get_first_item_by_entry(tool):
                    self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_TOTEMS)
                    return False

            # Check if player inventory has space left.
            for item, count in casting_spell.get_conjured_items():
                if item == 0:
                    break

                item_template = WorldDatabaseManager.ItemTemplateHolder.item_template_get_by_entry(item)
                error = self.unit_mgr.inventory.can_store_item(item_template, count)
                if error != InventoryError.BAG_OK:
                    self.unit_mgr.inventory.send_equip_error(error)
                    self.send_cast_result(casting_spell.spell_entry.ID, SpellCheckCastResult.SPELL_FAILED_DONT_REPORT)
                    return False

        return True

    def consume_resources_for_cast(self, casting_spell):  # This method assumes that the reagents exist (meets_casting_requisites was run).
        power_type = casting_spell.spell_entry.PowerType
        cost = casting_spell.get_resource_cost()
        current_power = self.unit_mgr.health if power_type == PowerTypes.TYPE_HEALTH else self.unit_mgr.get_power_type_value()
        new_power = current_power - cost
        if power_type == PowerTypes.TYPE_MANA:
            self.unit_mgr.set_mana(new_power)
        elif power_type == PowerTypes.TYPE_RAGE:
            self.unit_mgr.set_rage(new_power)
        elif power_type == PowerTypes.TYPE_FOCUS:
            self.unit_mgr.set_focus(new_power)
        elif power_type == PowerTypes.TYPE_ENERGY:
            self.unit_mgr.set_energy(new_power)
        elif power_type == PowerTypes.TYPE_HEALTH:
            self.unit_mgr.set_health(new_power)

        if self.unit_mgr.get_type() == ObjectTypes.TYPE_PLAYER and \
                casting_spell.requires_combo_points():
            self.unit_mgr.remove_combo_points()
            self.unit_mgr.set_dirty()

        for reagent_info in casting_spell.get_reagents():  # Reagents.
            if reagent_info[0] == 0:
                break
            self.unit_mgr.inventory.remove_items(reagent_info[0], reagent_info[1])

        # Spells cast with consumables.
        if casting_spell.source_item and casting_spell.source_item.has_charges():
            spell_stats = casting_spell.get_item_spell_stats()
            charges = spell_stats.charges
            if charges < 0:  # Negative charges remove items.
                self.unit_mgr.inventory.remove_items(casting_spell.source_item.item_template.entry, 1)

            if charges != 0 and charges != -1:  # don't modify if no charges remain or this item is a consumable.
                new_charges = charges-1 if charges > 0 else charges+1
                spell_stats.charges = new_charges

        self.unit_mgr.set_dirty()

    def send_cast_result(self, spell_id, error):
        # TODO CAST_SUCCESS_KEEP_TRACKING
        #  cast_status = SpellCastStatus.CAST_SUCCESS if error == SpellCheckCastResult.SPELL_CAST_OK else SpellCastStatus.CAST_FAILED

        if self.unit_mgr.get_type() != ObjectTypes.TYPE_PLAYER:
            return

        if error == SpellCheckCastResult.SPELL_NO_ERROR:
            data = pack('<IB', spell_id, SpellCastStatus.CAST_SUCCESS)
        else:
            data = pack('<I2B', spell_id, SpellCastStatus.CAST_FAILED, error)

        self.unit_mgr.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_CAST_RESULT, data))
