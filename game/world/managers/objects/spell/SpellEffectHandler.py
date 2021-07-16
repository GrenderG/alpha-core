from database.world.WorldDatabaseManager import WorldDatabaseManager
from game.world.managers.abstractions.Vector import Vector
from game.world.managers.objects.ObjectManager import ObjectManager
from game.world.managers.objects.player.DuelManager import DuelManager
from game.world.managers.objects.spell.AuraManager import AppliedAura
from utils.Logger import Logger
from utils.constants.MiscCodes import ObjectTypes, HighGuid
from utils.constants.SpellCodes import SpellCheckCastResult, AuraTypes, SpellEffects, SpellState, SpellTargetMask
from utils.constants.UnitCodes import PowerTypes, UnitFlags, MovementTypes


class SpellEffectHandler(object):
    @staticmethod
    def apply_effect(casting_spell, effect, caster, target):
        if effect.effect_type not in SPELL_EFFECTS:
            Logger.debug(f'Unimplemented effect called: {effect.effect_type}')
            return
        SPELL_EFFECTS[effect.effect_type](casting_spell, effect, caster, target)

    @staticmethod
    def handle_school_damage(casting_spell, effect, caster, target):
        damage = effect.get_effect_points(casting_spell.caster_effective_level)
        caster.apply_spell_damage(target, damage, casting_spell)

    @staticmethod
    def handle_heal(casting_spell, effect, caster, target):
        healing = effect.get_effect_points(casting_spell.caster_effective_level)
        caster.apply_spell_healing(target, healing, casting_spell)

    @staticmethod
    def handle_weapon_damage(casting_spell, effect, caster, target):
        weapon_damage = caster.calculate_base_attack_damage(casting_spell.spell_attack_type, casting_spell.spell_entry.School,
                                                            target.creature_type, apply_bonuses=False)  # Bonuses are applied on spell damage

        damage = weapon_damage + effect.get_effect_points(casting_spell.caster_effective_level)
        caster.apply_spell_damage(target, damage, casting_spell)

    @staticmethod
    def handle_weapon_damage_plus(casting_spell, effect, caster, target):
        weapon_damage = caster.calculate_base_attack_damage(casting_spell.spell_attack_type, casting_spell.spell_entry.School,
                                                            target.creature_type, apply_bonuses=False)  # Bonuses are applied on spell damage

        damage_bonus = effect.get_effect_points(casting_spell.caster_effective_level)

        if caster.get_type() == ObjectTypes.TYPE_PLAYER and \
                casting_spell.requires_combo_points():
            damage_bonus *= caster.combo_points

        caster.apply_spell_damage(target, weapon_damage + damage_bonus, casting_spell)

    @staticmethod
    def handle_add_combo_points(casting_spell, effect, caster, target):
        caster.add_combo_points_on_target(target, effect.get_effect_points(casting_spell.caster_effective_level))

    @staticmethod
    def handle_aura_application(casting_spell, effect, caster, target):
        target.aura_manager.apply_spell_effect_aura(caster, casting_spell, effect)

    @staticmethod
    def handle_request_duel(casting_spell, effect, caster, target):
        duel_result = DuelManager.request_duel(caster, target, effect.misc_value)
        if duel_result == 1:
            result = SpellCheckCastResult.SPELL_NO_ERROR
        elif duel_result == 0:
            result = SpellCheckCastResult.SPELL_FAILED_TARGET_DUELING
        else:
            result = SpellCheckCastResult.SPELL_FAILED_DONT_REPORT
        caster.spell_manager.send_cast_result(casting_spell.spell_entry.ID, result)

    @staticmethod
    def handle_open_lock(casting_spell, effect, caster, target):
        # TODO Skill checks etc.
        if caster and target and target.get_type() == ObjectTypes.TYPE_GAMEOBJECT:  # TODO other object types, ie. lockboxes
            target.use(caster)
            casting_spell.cast_state = SpellState.SPELL_STATE_ACTIVE  # Keep checking movement interrupt.

    @staticmethod
    def handle_energize(casting_spell, effect, caster, target):
        power_type = effect.misc_value
        if power_type != target.power_type:
            return

        amount = effect.get_effect_points(casting_spell.caster_effective_level)
        target.receive_power(amount, power_type)

    @staticmethod
    def handle_summon_mount(casting_spell, effect, caster, target):
        already_mounted = target.unit_flags & UnitFlags.UNIT_MASK_MOUNTED
        if already_mounted:
            # Remove any existing mount auras.
            target.aura_manager.remove_auras_by_type(AuraTypes.SPELL_AURA_MOUNTED)
            target.aura_manager.remove_auras_by_type(AuraTypes.SPELL_AURA_MOD_INCREASE_MOUNTED_SPEED)
            # Force dismount if target is still mounted (like a previous SPELL_EFFECT_SUMMON_MOUNT that doesn't
            # leave any applied aura).
            if target.mount_display_id > 0:
                target.unmount()
                target.set_dirty()
        else:
            creature_entry = effect.misc_value
            if not target.summon_mount(creature_entry):
                Logger.error(f'SPELL_EFFECT_SUMMON_MOUNT: Creature template ({creature_entry}) not found in database.')

    @staticmethod
    def handle_insta_kill(casting_spell, effect, caster, target):
        # No SMSG_SPELLINSTAKILLLOG in 0.5.3
        target.die(killer=caster)

    @staticmethod
    def handle_create_item(casting_spell, effect, caster, target):
        if target.get_type() != ObjectTypes.TYPE_PLAYER:
            return

        target.inventory.add_item(effect.item_type,
                                  count=effect.get_effect_points(casting_spell.caster_effective_level))

    @staticmethod
    def handle_teleport_units(casting_spell, effect, caster, target):
        teleport_targets = effect.targets.get_resolved_effect_targets_by_type(tuple)  # Teleport targets should follow the format (map, Vector)
        if len(teleport_targets) == 0:
            return
        teleport_info = teleport_targets[0]
        if len(teleport_info) != 2 or not isinstance(teleport_info[1], Vector):
            return

        target.teleport(teleport_info[0], teleport_info[1])  # map, coordinates resolved
        # TODO Die sides are assigned for at least Word of Recall (ID 1)

    @staticmethod
    def handle_persistent_area_aura(casting_spell, effect, caster, target):  # Ground-targeted aoe
        if target is not None:
            return

        SpellEffectHandler.handle_apply_area_aura(casting_spell, effect, caster, target)
        return

    @staticmethod
    def handle_apply_area_aura(casting_spell, effect, caster, target):  # Paladin auras, healing stream totem etc.
        casting_spell.cast_state = SpellState.SPELL_STATE_ACTIVE

        previous_targets = effect.targets.previous_targets_a if effect.targets.previous_targets_a else []
        current_targets = effect.targets.resolved_targets_a

        new_targets = [unit for unit in current_targets if unit not in previous_targets]  # Targets that can't have the aura yet
        missing_targets = [unit for unit in previous_targets if unit not in current_targets]  # Targets that moved out of the area

        for target in new_targets:
            new_aura = AppliedAura(caster, casting_spell, effect, target)
            target.aura_manager.add_aura(new_aura)

        for target in missing_targets:
            target.aura_manager.cancel_auras_by_spell_id(casting_spell.spell_entry.ID)

    @staticmethod
    def handle_learn_spell(casting_spell, effect, caster, target):
        target_spell_id = effect.trigger_spell_id
        target.spell_manager.learn_spell(target_spell_id)

    @staticmethod
    def handle_summon_totem(casting_spell, effect, caster, target):
        totem_entry = effect.misc_value

        # TODO Temporary way to spawn creature
        creature_template = WorldDatabaseManager.creature_get_by_entry(totem_entry)
        from database.world.WorldModels import SpawnsCreatures
        instance = SpawnsCreatures()
        instance.spawn_id = HighGuid.HIGHGUID_UNIT + 1000  # TODO Placeholder GUID
        instance.map = caster.map_
        instance.orientation = target.o
        instance.position_x = target.x
        instance.position_y = target.y
        instance.position_z = target.z
        instance.spawntimesecsmin = 0
        instance.spawntimesecsmax = 0
        instance.health_percent = 100
        instance.mana_percent = 100
        instance.movement_type = MovementTypes.IDLE
        instance.spawn_flags = 0
        instance.visibility_mod = 0

        from game.world.managers.objects.creature.CreatureManager import CreatureManager
        creature_manager = CreatureManager(
            creature_template=creature_template,
            creature_instance=instance
        )
        creature_manager.faction = caster.faction

        creature_manager.load()
        creature_manager.set_dirty()
        creature_manager.respawn()

        # TODO This should be handled in creature AI instead
        # TODO Totems are not connected to player (pet etc. handling)
        for spell_id in [creature_template.spell_id1, creature_template.spell_id2, creature_template.spell_id3, creature_template.spell_id4]:
            if spell_id == 0:
                break
            creature_manager.spell_manager.handle_cast_attempt(spell_id, creature_manager, creature_manager, 0)

    @staticmethod
    def handle_script_effect(casting_spell, effect, caster, target):
        arcane_missiles = [5143, 5144, 5145, 6125]  # Only arcane missiles and group astral recall.
        group_astral_recall = 966
        if casting_spell.spell_entry.ID in arcane_missiles:
            # Periodic trigger spell aura uses the original target mask.
            # Arcane missiles initial cast is self-targeted, so we need to switch the mask here.
            casting_spell.spell_target_mask = SpellTargetMask.UNIT
        elif casting_spell.spell_entry.ID == group_astral_recall:
            for target in effect.targets.get_resolved_effect_targets_by_type(ObjectManager):
                if target.get_type() != ObjectTypes.TYPE_PLAYER:
                    continue
                recall_coordinates = target.get_deathbind_coordinates()
                target.teleport(recall_coordinates[0], recall_coordinates[1])

    AREA_SPELL_EFFECTS = [
        SpellEffects.SPELL_EFFECT_PERSISTENT_AREA_AURA,
        SpellEffects.SPELL_EFFECT_APPLY_AREA_AURA
    ]


SPELL_EFFECTS = {
    SpellEffects.SPELL_EFFECT_SCHOOL_DAMAGE: SpellEffectHandler.handle_school_damage,
    SpellEffects.SPELL_EFFECT_HEAL: SpellEffectHandler.handle_heal,
    SpellEffects.SPELL_EFFECT_WEAPON_DAMAGE: SpellEffectHandler.handle_weapon_damage,
    SpellEffects.SPELL_EFFECT_ADD_COMBO_POINTS: SpellEffectHandler.handle_add_combo_points,
    SpellEffects.SPELL_EFFECT_DUEL: SpellEffectHandler.handle_request_duel,
    SpellEffects.SPELL_EFFECT_WEAPON_DAMAGE_PLUS: SpellEffectHandler.handle_weapon_damage_plus,
    SpellEffects.SPELL_EFFECT_APPLY_AURA: SpellEffectHandler.handle_aura_application,
    SpellEffects.SPELL_EFFECT_ENERGIZE: SpellEffectHandler.handle_energize,
    SpellEffects.SPELL_EFFECT_SUMMON_MOUNT: SpellEffectHandler.handle_summon_mount,
    SpellEffects.SPELL_EFFECT_INSTAKILL: SpellEffectHandler.handle_insta_kill,
    SpellEffects.SPELL_EFFECT_CREATE_ITEM: SpellEffectHandler.handle_create_item,
    SpellEffects.SPELL_EFFECT_TELEPORT_UNITS: SpellEffectHandler.handle_teleport_units,
    SpellEffects.SPELL_EFFECT_PERSISTENT_AREA_AURA: SpellEffectHandler.handle_persistent_area_aura,
    SpellEffects.SPELL_EFFECT_OPEN_LOCK: SpellEffectHandler.handle_open_lock,
    SpellEffects.SPELL_EFFECT_LEARN_SPELL: SpellEffectHandler.handle_learn_spell,
    SpellEffects.SPELL_EFFECT_APPLY_AREA_AURA: SpellEffectHandler.handle_apply_area_aura,
    SpellEffects.SPELL_EFFECT_SUMMON_TOTEM: SpellEffectHandler.handle_summon_totem,
    SpellEffects.SPELL_EFFECT_SCRIPT_EFFECT: SpellEffectHandler.handle_script_effect
}

