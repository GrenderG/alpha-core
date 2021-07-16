import time
from struct import pack

from game.world.managers.objects.spell.AppliedAura import AppliedAura
from game.world.managers.objects.spell.AuraEffectHandler import AuraEffectHandler
from network.packet.PacketWriter import PacketWriter, OpCode
from utils.constants.MiscCodes import ObjectTypes, ProcFlags, HitInfo
from utils.constants.SpellCodes import AuraTypes, AuraSlots, SpellEffects, SpellCheckCastResult, \
    SpellAuraInterruptFlags, SpellAttributes, SpellAttributesEx
from utils.constants.UnitCodes import UnitFlags, StandState
from utils.constants.UpdateFields import UnitFields


class AuraManager:
    def __init__(self, unit_mgr):
        self.unit_mgr = unit_mgr
        self.active_auras = {}  # (int: Aura) to have persistent indices.
        self.current_flags = 0x0

    def apply_spell_effect_aura(self, caster, casting_spell, spell_effect):
        aura = AppliedAura(caster, casting_spell, spell_effect, self.unit_mgr)
        self.add_aura(aura)

    def add_aura(self, aura):
        # Note: This order of applying, removing colliding and then returning might be problematic if cases are added to can_apply_aura.
        # At the moment mount behaviour depends on this order.
        can_apply = self.can_apply_aura(aura)
        self.remove_colliding_effects(aura)
        if not can_apply:
            return

        aura.index = self.get_next_aura_index(aura)
        self.active_auras[aura.index] = aura

        AuraEffectHandler.handle_aura_effect_change(aura, aura.target)

        if not aura.passive:
            self.write_aura_to_unit(aura)
            self.write_aura_flag_to_unit(aura)
            self.send_aura_duration(aura)

        # Aura application threat TODO handle threat elsewhere
        if aura.harmful:
            if aura.source_spell.generates_threat():
                self.unit_mgr.attack(aura.caster)
            self.check_aura_interrupts(negative_aura_applied=True)

        self.unit_mgr.set_dirty()

    has_moved = False  # Set from SpellManager - TODO pass movement info from unit update instead

    def update(self, timestamp):
        for aura in list(self.active_auras.values()):
            aura.update(timestamp)  # Update duration and handle periodic effects.
            if aura.has_duration() and aura.get_duration() <= 0:
                self.remove_aura(aura)

        if len(self.active_auras) > 0:
            self.check_aura_interrupts(has_moved=self.has_moved)
        self.has_moved = False

    def can_apply_aura(self, aura) -> bool:
        if aura.spell_effect.aura_type == AuraTypes.SPELL_AURA_MOD_SHAPESHIFT and \
                len(self.get_auras_by_spell_id(aura.spell_id)) > 0:
            return False  # Don't apply same shapeshift effect if it already exists.

        if aura.spell_effect.aura_type == AuraTypes.SPELL_AURA_MOUNTED and \
                aura.target.unit_flags & UnitFlags.UNIT_MASK_MOUNTED:
            return False

        if aura.spell_effect.aura_type == AuraTypes.SPELL_AURA_MOD_INCREASE_MOUNTED_SPEED and \
                aura.target.unit_flags & UnitFlags.UNIT_MASK_MOUNTED == 0:
            return False
        return True

    def check_aura_interrupts(self, has_moved=False, negative_aura_applied=False, cast_spell=False, received_damage=False):
        # TODO turning and water-related checks
        # Add once movement information is passed to update.
        flag_cases = {
            SpellAuraInterruptFlags.AURA_INTERRUPT_FLAG_ENTER_COMBAT: self.unit_mgr.in_combat,
            SpellAuraInterruptFlags.AURA_INTERRUPT_FLAG_NOT_MOUNTED: self.unit_mgr.unit_flags & UnitFlags.UNIT_MASK_MOUNTED,
            SpellAuraInterruptFlags.AURA_INTERRUPT_FLAG_MOVE: has_moved,
            SpellAuraInterruptFlags.AURA_INTERRUPT_FLAG_CAST: self.unit_mgr.spell_manager.is_casting() or cast_spell,
            SpellAuraInterruptFlags.AURA_INTERRUPT_FLAG_NEGATIVE_SPELL: negative_aura_applied,
            SpellAuraInterruptFlags.AURA_INTERRUPT_FLAG_DAMAGE: received_damage
        }
        for aura in list(self.active_auras.values()):
            for flag, condition in flag_cases.items():
                if aura.interrupt_flags & flag and condition:
                    self.remove_aura(aura)
                    continue

                # Food buffs are not labeled and an interrupt for sitting does not exist.
                # Food/drink spells do claim that the player must remain seated.
                # In later versions an aurainterrupt exists for this purpose.
                if aura.source_spell.is_refreshment_spell() and self.unit_mgr.stand_state != StandState.UNIT_SITTING:
                    self.remove_aura(aura)

    # Involved unit is the secondary unit in the proc event.
    # is_receiver is set to false if the player is causing damage and set to true if the player is taking damage.
    def check_aura_procs(self, involved_cast=None, killed_unit=False, damage_info=None, is_melee_swing=False):
        is_receiver = (damage_info and damage_info.target is self.unit_mgr) or \
                      (involved_cast and involved_cast.spell_caster is not self.unit_mgr)

        # Always pass the second unit as the effect target. The handler will choose the target based on the spell.
        if damage_info:
            effect_target = damage_info.attacker if is_receiver else damage_info.target
        elif involved_cast:
            # All targets for the spell could be passed, but this would only matter for ProcFlags.SPELL_CAST
            # SPELL_CAST is only used by one deprecated spell which will have the correct target in initial_target.
            effect_target = involved_cast.spell_caster if is_receiver else involved_cast.initial_target
        else:
            effect_target = self.unit_mgr

        flag_cases = {
            ProcFlags.DEAL_COMBAT_DMG: not is_receiver and damage_info and damage_info.total_damage > 0,  # -> cast on target.
            ProcFlags.TAKE_COMBAT_DMG: is_receiver and damage_info and damage_info.total_damage > 0,
            ProcFlags.KILL: killed_unit,
            ProcFlags.HEARTBEAT: True,  # TODO Not sure what expected behaviour is - call on every proc for now
            ProcFlags.DODGE: is_receiver and damage_info and damage_info.hit_info & HitInfo.DODGE,
            ProcFlags.PARRY: is_receiver and damage_info and damage_info.hit_info & HitInfo.PARRY,
            ProcFlags.BLOCK: is_receiver and damage_info and damage_info.hit_info & HitInfo.BLOCK,
            ProcFlags.SWING: not is_receiver and is_melee_swing,
            ProcFlags.SPELL_CAST: not is_receiver and involved_cast,  # Only used by zzOLDMind Bomb.
            ProcFlags.SPELL_HIT: is_receiver and involved_cast,
        }
        for aura in list(self.active_auras.values()):
            flags = aura.source_spell.spell_entry.ProcFlags
            if not flags:
                continue

            for proc_flag, condition in flag_cases.items():
                if proc_flag & flags and condition and aura.proc_charges != 0:  # Proc charges are set to -1 for auras with no charges so check for 0.
                    # Remove charge before trigger to avoid infinite loops with procs.
                    aura.proc_charges -= 1
                    AuraEffectHandler.handle_aura_effect_change(aura, effect_target, is_proc=True)

                if aura.proc_charges == 0:
                    self.remove_aura(aura)

    def remove_colliding_effects(self, aura):
        # Special case with SpellEffect mounting and mounting by aura
        if aura.spell_effect.aura_type == AuraTypes.SPELL_AURA_MOUNTED and \
                aura.target.unit_flags & UnitFlags.UNIT_MASK_MOUNTED and not \
                self.get_auras_by_type(AuraTypes.SPELL_AURA_MOUNTED):
            AuraEffectHandler.handle_mounted(aura, aura.target, remove=True)  # Remove mount effect

        aura_spell_template = aura.source_spell.spell_entry
        aura_effect_index = aura.spell_effect.effect_index
        caster_guid = aura.caster.guid

        for applied_aura in list(self.active_auras.values()):
            is_similar = applied_aura.source_spell.spell_entry == aura_spell_template and \
                         applied_aura.spell_effect.effect_index == aura_effect_index  # Spell and effect are the same
            # Source doesn't matter for unique auras
            is_unique = applied_aura.source_spell.spell_entry.AttributesEx & SpellAttributesEx.SPELL_ATTR_EX_AURA_UNIQUE

            if is_similar and (is_unique or applied_aura.caster.guid == caster_guid):
                self.remove_aura(applied_aura)

            if applied_aura.spell_effect.aura_type == AuraTypes.SPELL_AURA_MOD_SHAPESHIFT and \
                    aura.spell_effect.aura_type == AuraTypes.SPELL_AURA_MOD_SHAPESHIFT:
                self.remove_aura(applied_aura)  # Player can only be in one shapeshift form
                continue

    def get_auras_by_spell_id(self, spell_id) -> list[AppliedAura]:
        auras = []
        for aura in self.active_auras.values():
            if aura.spell_id != spell_id:
                continue
            auras.append(aura)
        return auras

    def get_auras_by_type(self, aura_type) -> list[AppliedAura]:
        auras = []
        for aura in list(self.active_auras.values()):
            if aura.spell_effect.aura_type != aura_type:
                continue
            auras.append(aura)
        return auras

    def remove_auras_by_type(self, aura_type):
        for aura in list(self.active_auras.values()):
            if aura.spell_effect.aura_type != aura_type:
                continue
            self.remove_aura(aura)

    def handle_death(self):
        persistent_flags = SpellAttributes.SPELL_ATTR_ALLOW_CAST_WHILE_DEAD | SpellAttributes.SPELL_ATTR_PASSIVE
        for aura in list(self.active_auras.values()):
            if aura.source_spell.spell_entry.Attributes & persistent_flags:
                continue
            self.remove_aura(aura)

    def remove_harmful_auras_by_caster(self, caster_guid):
        for aura in list(self.active_auras.values()):
            if aura.harmful and aura.caster.guid == caster_guid:
                self.remove_aura(aura)

    def remove_aura(self, aura, canceled=False):
        AuraEffectHandler.handle_aura_effect_change(aura, aura.target, remove=True)
        if not self.active_auras.pop(aura.index, None):
            return
        # Some area effect auras (paladin auras, tranq etc.) are tied to spell effects. Cancel cast on aura cancel, canceling the auras as well.
        self.unit_mgr.spell_manager.remove_cast(aura.source_spell, interrupted=canceled)

        # Some spells start cooldown on aura remove, handle that case here.
        if aura.source_spell.trigger_cooldown_on_aura_remove():
            self.unit_mgr.spell_manager.set_on_cooldown(aura.source_spell, start_locked_cooldown=True)

        if aura.passive:
            return  # Passive auras aren't written to unit.

        self.write_aura_to_unit(aura, clear=True)
        self.write_aura_flag_to_unit(aura, clear=True)
        self.unit_mgr.set_dirty()

    def remove_all_auras(self):
        for aura in list(self.active_auras.values()):
            self.remove_aura(aura)

    def cancel_auras_by_spell_id(self, spell_id):
        auras = self.get_auras_by_spell_id(spell_id)

        for aura in auras:
            self.remove_aura(aura, canceled=True)

    def handle_player_cancel_aura_request(self, spell_id):
        auras = self.get_auras_by_spell_id(spell_id)
        can_remove = True
        is_passive = True  # Player shouldn't be able to remove auras with only a passive part.
        for aura in auras:
            if not aura.passive:
                is_passive = False
            if aura.harmful or aura.source_spell.spell_entry.Attributes & SpellAttributes.SPELL_ATTR_CANT_CANCEL:
                can_remove = False  # Can't remove harmful auras.
                break

        if is_passive or not can_remove:
            return

        self.cancel_auras_by_spell_id(spell_id)

    def send_aura_duration(self, aura):
        if self.unit_mgr.get_type() != ObjectTypes.TYPE_PLAYER:
            return

        data = pack('<Bi', aura.index, int(aura.get_duration()))
        self.unit_mgr.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_UPDATE_AURA_DURATION, data))

    def write_aura_to_unit(self, aura, clear=False):
        field_index = UnitFields.UNIT_FIELD_AURA + aura.index
        self.unit_mgr.set_uint32(field_index, aura.spell_id if not clear else 0)

    def write_aura_flag_to_unit(self, aura, clear=False):
        if not aura:
            return
        byte = (aura.index & 7) << 2  # magic value for AuraFlags.
        if not clear:
            self.current_flags |= 0x9 << byte  # OR to current flags - from other server's source.
        else:
            self.current_flags &= ~(0x9 << byte)

        self.unit_mgr.set_uint32(UnitFields.UNIT_FIELD_AURAFLAGS + (aura.index >> 3), self.current_flags)

    def get_next_aura_index(self, aura) -> int:
        if aura.passive:
            min_index = AuraSlots.AURA_SLOT_PASSIVE_AURA_START
            max_index = AuraSlots.AURA_SLOT_END
        elif aura.harmful:
            min_index = AuraSlots.AURA_SLOT_HARMFUL_AURA_START
            max_index = AuraSlots.AURA_SLOT_PASSIVE_AURA_START
        else:
            min_index = AuraSlots.AURA_SLOT_POSITIVE_AURA_START
            max_index = AuraSlots.AURA_SLOT_HARMFUL_AURA_START

        for i in range(min_index, max_index):
            if i not in self.active_auras:
                return i
        return min_index  # No aura slots free, return first possible. TODO Some kind of priority system?
