from game.world.managers.abstractions.Vector import Vector
from game.world.managers.objects.ObjectManager import ObjectManager
from utils.Logger import Logger
from utils.constants.ObjectCodes import ObjectTypes
from utils.constants.SpellCodes import SpellImplicitTargets, SpellMissReason


class TargetMissInfo:
    def __init__(self, target, result):
        self.target = target
        self.result = result


class EffectTargets:
    def __init__(self, casting_spell, spell_effect):
        self.initial_target = casting_spell.initial_target
        self.caster = casting_spell.spell_caster
        self.casting_spell = casting_spell

        self.simple_targets = self.get_simple_targets()

        self.target_effect = spell_effect
        self.resolved_targets_a = None
        self.resolved_targets_b = None

    def get_simple_targets(self):
        target_is_player = self.casting_spell.initial_target_is_player()
        target_is_gameobject = self.casting_spell.initial_target_is_gameobject()
        target_is_item = self.casting_spell.initial_target_is_item()
        target_is_friendly = self.casting_spell.initial_target_is_unit_or_player() and \
            self.caster.is_friendly_to(self.casting_spell.initial_target)

        return {
            SpellImplicitTargets.TARGET_NOTHING: None,
            SpellImplicitTargets.TARGET_SELF: self.caster,
            SpellImplicitTargets.TARGET_PET: None,  # TODO
            SpellImplicitTargets.TARGET_CHAIN_DAMAGE: self.initial_target,  # TODO - resolve chain targets
            SpellImplicitTargets.TARGET_INNKEEPER_COORDINATES: self.caster.get_deathbind_coordinates() if target_is_player else None,
            SpellImplicitTargets.TARGET_SELECTED_FRIEND: self.initial_target if target_is_friendly else None,
            SpellImplicitTargets.TARGET_SELECTED_GAMEOBJECT: self.initial_target if target_is_gameobject else None,
            SpellImplicitTargets.TARGET_DUEL_VS_PLAYER: self.initial_target,  # Spells that can be cast on both hostile and friendly?
            SpellImplicitTargets.TARGET_GAMEOBJECT_AND_ITEM: self.initial_target if target_is_gameobject or target_is_item else None,
            SpellImplicitTargets.TARGET_MASTER: None,  # TODO
            SpellImplicitTargets.TARGET_MINION: None,  # TODO
            SpellImplicitTargets.TARGET_SELF_FISHING: self.caster
        }

    def resolve_implicit_targets_reference(self, implicit_target):
        target = self.simple_targets[implicit_target] if implicit_target in self.simple_targets else TARGET_RESOLVERS[implicit_target](self.casting_spell)

        if target is None and implicit_target != 0:  # Avoid crash on unfinished implementation while target resolving isn't finished TODO
            Logger.warning(f'Implicit target {implicit_target} resolved to None. Falling back to initial target or self.')
            target = self.initial_target if self.casting_spell.initial_target_is_object() else self.caster

        if type(target) is not list:
            return [target]
        return target

    def resolve_targets(self):
        self.resolved_targets_a = self.resolve_implicit_targets_reference(self.target_effect.implicit_target_a)
        self.resolved_targets_b = self.resolve_implicit_targets_reference(self.target_effect.implicit_target_b)

    def get_effect_target_results(self):
        targets = self.resolved_targets_a  # TODO B?
        target_info = {}
        for target in targets:
            if isinstance(target, ObjectManager):
                target_info[target.guid] = TargetMissInfo(target, SpellMissReason.MISS_REASON_NONE)  # TODO Misses etc.
        return target_info

    @staticmethod
    def resolve_random_enemy_chain_in_area(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_area_effect_custom(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_unit_near_caster(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_all_enemy_in_area(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_all_enemy_in_area_instant(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_table_coordinates(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_effect_select(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_party_around_caster(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_selected_friend(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_enemy_around_caster(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_infront(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_aoe_enemy_channel(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_all_friendly_around_caster(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_all_friendly_in_area(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_all_party(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_party_around_caster_2(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_single_party(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_aoe_party(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_script(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_gameobject_script_near_caster(casting_spell):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')


TARGET_RESOLVERS = {
    SpellImplicitTargets.TARGET_RANDOM_ENEMY_CHAIN_IN_AREA: EffectTargets.resolve_random_enemy_chain_in_area,
    SpellImplicitTargets.TARGET_UNIT_NEAR_CASTER: EffectTargets.resolve_unit_near_caster,
    SpellImplicitTargets.TARGET_AREAEFFECT_CUSTOM: EffectTargets.resolve_area_effect_custom,
    SpellImplicitTargets.TARGET_ALL_ENEMY_IN_AREA: EffectTargets.resolve_all_enemy_in_area,
    SpellImplicitTargets.TARGET_ALL_ENEMY_IN_AREA_INSTANT: EffectTargets.resolve_all_enemy_in_area_instant,
    SpellImplicitTargets.TARGET_TABLE_X_Y_Z_COORDINATES: EffectTargets.resolve_table_coordinates,
    SpellImplicitTargets.TARGET_EFFECT_SELECT: EffectTargets.resolve_effect_select,
    SpellImplicitTargets.TARGET_AROUND_CASTER_PARTY: EffectTargets.resolve_party_around_caster,
    SpellImplicitTargets.TARGET_SELECTED_FRIEND: EffectTargets.resolve_selected_friend,
    SpellImplicitTargets.TARGET_AROUND_CASTER_ENEMY: EffectTargets.resolve_enemy_around_caster,
    SpellImplicitTargets.TARGET_INFRONT: EffectTargets.resolve_infront,
    SpellImplicitTargets.TARGET_AREA_EFFECT_ENEMY_CHANNEL: EffectTargets.resolve_aoe_enemy_channel,
    SpellImplicitTargets.TARGET_ALL_FRIENDLY_UNITS_AROUND_CASTER: EffectTargets.resolve_all_friendly_around_caster,
    SpellImplicitTargets.TARGET_ALL_FRIENDLY_UNITS_IN_AREA: EffectTargets.resolve_all_friendly_in_area,
    SpellImplicitTargets.TARGET_ALL_PARTY: EffectTargets.resolve_all_party,
    SpellImplicitTargets.TARGET_ALL_PARTY_AROUND_CASTER_2: EffectTargets.resolve_party_around_caster_2,
    SpellImplicitTargets.TARGET_SINGLE_PARTY: EffectTargets.resolve_single_party,
    SpellImplicitTargets.TARGET_AREAEFFECT_PARTY: EffectTargets.resolve_aoe_party,
    SpellImplicitTargets.TARGET_SCRIPT: EffectTargets.resolve_script,
    SpellImplicitTargets.TARGET_GAMEOBJECT_SCRIPT_NEAR_CASTER: EffectTargets.resolve_gameobject_script_near_caster
}
