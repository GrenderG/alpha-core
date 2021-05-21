from game.world.managers.maps.MapManager import MapManager
from game.world.managers.objects.ObjectManager import ObjectManager
from utils.Logger import Logger
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

        self.previous_targets_a = None
        self.previous_targets_b = None  # Used for non-persistent targets (aoe effects etc.)

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
            SpellImplicitTargets.TARGET_CHAIN_DAMAGE: self.initial_target if not target_is_friendly else None,  # TODO - resolve chain targets
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
        target = self.simple_targets[implicit_target] if implicit_target in self.simple_targets else TARGET_RESOLVERS[implicit_target](self.casting_spell, self.target_effect)

        if target is None and implicit_target != 0:  # Avoid crash on unfinished implementation while target resolving isn't finished TODO
            Logger.warning(f'Implicit target {implicit_target} resolved to None. Falling back to initial target or self.')
            target = self.initial_target if self.casting_spell.initial_target_is_object() else self.caster

        if type(target) is not list:
            return [target]
        return target

    def can_target_friendly(self):
        return self.target_effect.implicit_target_a in FRIENDLY_IMPLICIT_TARGETS or \
               self.target_effect.implicit_target_b in FRIENDLY_IMPLICIT_TARGETS

    def resolve_targets(self):
        self.previous_targets_a = self.resolved_targets_a
        self.previous_targets_b = self.resolved_targets_b
        self.resolved_targets_a = self.resolve_implicit_targets_reference(self.target_effect.implicit_target_a)
        self.resolved_targets_b = self.resolve_implicit_targets_reference(self.target_effect.implicit_target_b)

    def get_effect_target_results(self):
        targets = self.get_final_effect_targets()
        # At least some B targets act as specifying on A. No table for now for ImplicitTarget values that act as specifiers, so prefer B if values exist
        # TODO if issues arise, add table for specifying ImplicitTargets
        target_info = {}
        for target in targets:
            if isinstance(target, ObjectManager):
                target_info[target.guid] = TargetMissInfo(target, SpellMissReason.MISS_REASON_NONE)  # TODO Misses etc.
        return target_info

    def get_final_effect_targets(self):
        return self.resolved_targets_b if len(self.resolved_targets_b) > 0 else self.resolved_targets_a

    @staticmethod
    def resolve_random_enemy_chain_in_area(casting_spell, target_effect):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_area_effect_custom(casting_spell, target_effect):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_unit_near_caster(casting_spell, target_effect):
        result = MapManager.get_surrounding_units(casting_spell.spell_caster, True)
        units = list(result[0].values()) + list(result[1].values())

        closest_info = -1, None
        caster = casting_spell.spell_caster
        for unit in units:
            if caster is unit:
                continue
            new_distance = caster.location.distance(unit.location)
            if closest_info[0] == -1 or new_distance < closest_info[0]:
                closest_info = new_distance, unit

        if closest_info[0] > casting_spell.range_entry.RangeMax:
            return None

        return closest_info[1]

    # Besides a couple test spells, this target seems to only be used in TargetB with TargetA
    # TargetA resolves the units in the area, and this seems to act as a filter for enemies
    # ie. war stomp - ImplicitTargetA_1 = TARGET_ALL_AROUND_CASTER, B_1 = TARGET_ALL_ENEMY_IN_AREA
    # For the sake of completeness (test spells), we'll fall back to around caster if this is used in A
    @staticmethod
    def resolve_all_enemy_in_area(casting_spell, target_effect):
        resolved_a = target_effect.targets.resolved_targets_a

        if not target_effect.implicit_target_a:  # see notes
            resolved_a = EffectTargets.resolve_all_around_caster(casting_spell, target_effect)

        enemy_units = []
        for unit in resolved_a:
            if not casting_spell.spell_caster.is_friendly_to(unit):
                enemy_units.append(unit)

        return enemy_units

    @staticmethod
    def resolve_all_enemy_in_area_instant(casting_spell, target_effect):
        target = casting_spell.initial_target
        if not casting_spell.initial_target_is_terrain():
            return []
        map_ = casting_spell.spell_caster.map_
        result = MapManager.get_surrounding_units_by_location(target, map_, target_effect.get_radius(), True)

        merged = list(result[0].values()) + list(result[1].values())
        enemies = []
        for unit in merged:
            if casting_spell.spell_caster.is_friendly_to(unit):
                continue
            enemies.append(unit)
        return enemies

    @staticmethod
    def resolve_table_coordinates(casting_spell, target_effect):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_effect_select(casting_spell, target_effect):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_party_around_caster(casting_spell, target_effect):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_selected_friend(casting_spell, target_effect):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    # Never used in B
    @staticmethod
    def resolve_all_around_caster(casting_spell, target_effect):
        result = MapManager.get_surrounding_units(casting_spell.spell_caster, True)
        units = list(result[0].values()) + list(result[1].values())

        caster = casting_spell.spell_caster
        units_in_range = []
        for unit in units:
            if caster is unit:
                continue
            distance = caster.location.distance(unit.location)
            if distance <= target_effect.get_radius():
                units_in_range.append(unit)

        return units_in_range

    @staticmethod
    def resolve_infront(casting_spell, target_effect):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_aoe_enemy_channel(casting_spell, target_effect):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_all_friendly_around_caster(casting_spell, target_effect):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_all_friendly_in_area(casting_spell, target_effect):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_all_party(casting_spell, target_effect):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_party_around_caster_2(casting_spell, target_effect):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_single_party(casting_spell, target_effect):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_aoe_party(casting_spell, target_effect):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_script(casting_spell, target_effect):
        Logger.warning(f'Unimlemented implicit target called for spell {casting_spell.spell_entry.ID}')

    @staticmethod
    def resolve_gameobject_script_near_caster(casting_spell, target_effect):
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
    SpellImplicitTargets.TARGET_ALL_AROUND_CASTER: EffectTargets.resolve_all_around_caster,
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

FRIENDLY_IMPLICIT_TARGETS = [
    SpellImplicitTargets.TARGET_PET,
    # SpellImplicitTargets.TARGET_EFFECT_SELECT  # All self casts except one hostile aoe
    SpellImplicitTargets.TARGET_AROUND_CASTER_PARTY,
    SpellImplicitTargets.TARGET_SELECTED_FRIEND,
    # SpellImplicitTargets.TARGET_INFRONT,  # Only hostile
    # SpellImplicitTargets.TARGET_DUEL_VS_PLAYER = 25  # Can target both - resolved by checking target hostility
    SpellImplicitTargets.TARGET_MASTER,
    SpellImplicitTargets.TARGET_ALL_FRIENDLY_UNITS_AROUND_CASTER,
    SpellImplicitTargets.TARGET_ALL_FRIENDLY_UNITS_IN_AREA,
    SpellImplicitTargets.TARGET_MINION,
    SpellImplicitTargets.TARGET_ALL_PARTY,
    SpellImplicitTargets.TARGET_ALL_PARTY_AROUND_CASTER_2,
    SpellImplicitTargets.TARGET_SINGLE_PARTY,
    SpellImplicitTargets.TARGET_AREAEFFECT_PARTY,  # Power infuses the target's party increasing their Shadow resistance by $s1 for $d.
    # SpellImplicitTargets.TARGET_SCRIPT = 38  # Resolved separately
]
